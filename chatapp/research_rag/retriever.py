from functools import lru_cache
from typing import Any, Dict, List

from .embeddings import EmbeddingManager, get_embedder
from .vector_store import VectorStore, get_vector_store


class RAGRetriever:
    """Handles query-based retrieval from the vector store."""

    def __init__(self, vector_store: VectorStore, embedding_manager: EmbeddingManager):
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager

    def retrieve(
        self,
        query: str,
        owner_id: int,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the chunks most relevant to a query, from one user's papers only.

        Args:
            query: The search query
            owner_id: Id of the user whose papers are searched
            top_k: Number of top results to return
            score_threshold: Minimum similarity score (cosine, -1 to 1) to keep a result

        Returns:
            List of dicts with id, content, metadata, similarity_score, distance, rank
        """
        if not query.strip():
            raise ValueError("Query is empty.")

        print(f"Retrieving documents for query: '{query}'")
        print(f"Owner: {owner_id}, Top K: {top_k}, Score threshold: {score_threshold}")

        query_embedding = self.embedding_manager.generate_embeddings([query])[0]
        results = self.vector_store.search(query_embedding, owner_id=owner_id, k=top_k)

        retrieved_docs = []
        documents = results["documents"][0]

        if not documents:
            print("No documents found")
            return retrieved_docs

        for i, (doc_id, document, metadata, distance) in enumerate(
            zip(results["ids"][0], documents, results["metadatas"][0], results["distances"][0]),
            start=1,
        ):
            # FAISS returns squared L2 distance. For unit-length vectors
            # (all-MiniLM-L6-v2), cosine similarity = 1 - distance / 2.
            similarity_score = 1 - distance / 2

            if similarity_score >= score_threshold:
                retrieved_docs.append({
                    "id": doc_id,
                    "content": document,
                    "metadata": metadata,
                    "similarity_score": similarity_score,
                    "distance": distance,
                    "rank": i,
                })

        print(f"Retrieved {len(retrieved_docs)} documents (after filtering)")
        return retrieved_docs


@lru_cache(maxsize=1)
def get_retriever() -> RAGRetriever:
    return RAGRetriever(get_vector_store(), get_embedder())