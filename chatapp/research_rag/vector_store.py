
import os
import pickle
from pathlib import Path
from typing import Any, List
from functools import lru_cache

import faiss
import numpy as np
from django.conf import settings


class VectorStore:
    def __init__(
        self,
        collection_name: str = "pdf_documents",
        persist_directory: str = "../data/vector_store",
    ):
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.index_path = self.persist_directory / "index.faiss"
        self.records_path = self.persist_directory / "records.pkl"

        self.records = {}

        if self.index_path.exists() and self.records_path.exists():
            self.index = faiss.read_index(str(self.index_path))

            with open(self.records_path, "rb") as file:
                self.records = pickle.load(file)

            if self.index.ntotal != len(self.records):
                raise RuntimeError(
                    "FAISS index and metadata record counts do not match."
                )

            print(f"FAISS loaded: {self.index.ntotal} chunks")

        elif self.index_path.exists() or self.records_path.exists():
            raise RuntimeError(
                "FAISS files are incomplete. Remove both files "
                "and rebuild the index through PDF ingestion."
            )

        else:
            # all-MiniLM-L6-v2 produces 384-dimensional embeddings.
            self.index = faiss.IndexIDMap2(
                faiss.IndexFlatL2(384)
            )
            print("Created a fresh FAISS vector store.")

        self.next_id = max(self.records.keys(), default=-1) + 1

    def _save(self):
        index_temp = self.persist_directory / "index.tmp"
        records_temp = self.persist_directory / "records.tmp"

        faiss.write_index(self.index, str(index_temp))

        with open(records_temp, "wb") as file:
            pickle.dump(self.records, file)

        os.replace(index_temp, self.index_path)
        os.replace(records_temp, self.records_path)

    def add_documents(
        self,
        documents: List[Any],
        embeddings: np.ndarray,
    ):
        if not documents:
            return

        embeddings = np.asarray(embeddings, dtype=np.float32)

        if embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D array.")

        if len(documents) != len(embeddings):
            raise ValueError(
                "The number of documents and embeddings must match."
            )

        if embeddings.shape[1] != self.index.d:
            raise ValueError(
                f"Expected {self.index.d}-dimensional embeddings, "
                f"received {embeddings.shape[1]}."
            )

        if not np.isfinite(embeddings).all():
            raise ValueError("Embeddings contain invalid numeric values.")

        # Replace old chunks belonging to these papers.
        paper_ids = {
            str(doc.metadata["paper_id"])
            for doc in documents
        }

        for paper_id in paper_ids:
            self.delete_paper(paper_id)

        vector_ids = []
        new_records = {}

        for doc, embedding in zip(documents, embeddings):
            vector_id = self.next_id
            self.next_id += 1

            metadata = dict(doc.metadata)
            metadata["doc_index"] = len(new_records)
            metadata["content_length"] = len(doc.page_content)

            new_records[vector_id] = {
                "id": (
                    f"paper{metadata['paper_id']}_"
                    f"chunk{metadata['doc_index']}"
                ),
                "metadata": metadata,
                "document": doc.page_content,
            }

            vector_ids.append(vector_id)

        self.index.add_with_ids(
            embeddings,
            np.asarray(vector_ids, dtype=np.int64),
        )

        self.records.update(new_records)
        self._save()

        print(
            f"Added {len(vector_ids)} chunks. "
            f"Total in index: {self.index.ntotal}"
        )

    def delete_paper(self, paper_id: int):
        matching_ids = [
            vector_id
            for vector_id, record in self.records.items()
            if str(record["metadata"].get("paper_id")) == str(paper_id)
        ]

        if not matching_ids:
            return

        self.index.remove_ids(
            np.asarray(matching_ids, dtype=np.int64)
        )

        for vector_id in matching_ids:
            del self.records[vector_id]

        self._save()

    def search(
        self,
        query_embedding: np.ndarray,
        owner_id: int,
        k: int = 5,
    ):
        results = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        if self.index.ntotal == 0 or k <= 0:
            return results

        query = np.asarray(
            query_embedding, dtype=np.float32
        ).reshape(1, -1)

        if query.shape[1] != self.index.d:
            raise ValueError(
                f"Expected {self.index.d}-dimensional query embedding."
            )

        # Search all vectors, then filter by owner.
        # This avoids missing a user's results because another user
        # has closer vectors.
        distances, indices = self.index.search(
            query, self.index.ntotal
        )

        for distance, vector_id in zip(
            distances[0], indices[0]
        ):
            if vector_id == -1:
                continue

            record = self.records.get(int(vector_id))

            if record is None:
                continue

            metadata = record["metadata"]

            if str(metadata.get("owner_id")) != str(owner_id):
                continue

            results["ids"][0].append(record["id"])
            results["documents"][0].append(record["document"])
            results["metadatas"][0].append(metadata)
            results["distances"][0].append(float(distance))

            if len(results["ids"][0]) >= k:
                break

        return results

    def chunk_counts_by_paper(
        self,
        owner_id: int = None,
    ) -> dict:
        counts = {}

        for record in self.records.values():
            metadata = record["metadata"]

            if (
                owner_id is not None
                and str(metadata.get("owner_id")) != str(owner_id)
            ):
                continue

            paper_id = metadata["paper_id"]
            counts[paper_id] = counts.get(paper_id, 0) + 1

        return counts


@lru_cache(maxsize=1)
def get_vector_store():
    return VectorStore(
        persist_directory=str(settings.BASE_DIR / "vectorstore")
    )
