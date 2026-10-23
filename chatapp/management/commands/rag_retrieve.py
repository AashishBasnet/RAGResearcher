
import os

from dotenv import load_dotenv
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from langchain_groq import ChatGroq

from chatapp.research_rag.retriever import get_retriever


load_dotenv()


# ---- Edit these and re-run -----------------------------------------------
USERNAME = "admin"
QUERY = "How does dark matter scattering influence gas cooling?"
TOP_K = 5
SCORE_THRESHOLD = 0.35
RETURN_CONTEXT = True
# --------------------------------------------------------------------------


def rag_advanced(
    query,
    retriever,
    llm,
    owner_id,
    top_k=5,
    min_score=0.35,
    return_context=False,
):
    """
    Retrieve relevant research-paper chunks and generate an answer.

    Returns:
        answer: Generated answer
        sources: Retrieved source information
        confidence: Highest retrieval similarity score
        context: Full retrieved context, if requested
    """

    results = retriever.retrieve(
        query,
        owner_id=owner_id,
        top_k=top_k,
        score_threshold=min_score,
    )

    if not results:
        output = {
            "answer": "No relevant context found in the uploaded papers.",
            "sources": [],
            "confidence": 0.0,
        }

        if return_context:
            output["context"] = ""

        return output

    # Prepare context
    context = "\n\n".join(
        doc["content"] for doc in results
    )

    # Prepare source information
    sources = []

    for doc in results:
        metadata = doc.get("metadata", {})
        content = doc.get("content", "")

        sources.append({
            "source": metadata.get(
                "source_file",
                metadata.get(
                    "source",
                    metadata.get("paper_title", "Unknown"),
                ),
            ),
            "page": metadata.get(
                "page_label",
                metadata.get("page", "Unknown"),
            ),
            "score": doc.get("similarity_score", 0.0),
            "preview": content[:300] + (
                "..." if len(content) > 300 else ""
            ),
        })

    # Highest retrieval similarity, not answer correctness
    confidence = max(
        doc.get("similarity_score", 0.0)
        for doc in results
    )

    # Prompt the LLM to stay grounded in the retrieved papers
    prompt = f"""
You are ResearchQA, an assistant that answers questions using
the supplied research-paper excerpts.

Instructions:
- Answer using only information supported by the context.
- If the context does not sufficiently answer the question,
  say: "I couldn't find sufficient information to answer this
  question in the uploaded research papers."
- If the question is unrelated to the context, do not answer it
  using general knowledge.
- Be concise, clear, and factual.
- Cite the paper title and page number when the information
  is available in the context.
- Do not invent citations or unsupported claims.

Context:
{context}

Question:
{query}

Answer:
"""

    response = llm.invoke(prompt)

    answer = (
        response.content
        if hasattr(response, "content")
        else str(response)
    )

    output = {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }

    if return_context:
        output["context"] = context

    return output


class Command(BaseCommand):
    help = (
        "Retrieve research-paper chunks and generate "
        "an answer using the Groq LLM."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        # Check the user
        try:
            user = User.objects.get(username=USERNAME)
        except User.DoesNotExist:
            raise CommandError(
                f"No user named {USERNAME!r}. "
                "Edit USERNAME in this file."
            )

        # Initialize retriever
        retriever = get_retriever()

        # Initialize Groq LLM
        groq_api_key = os.getenv("GROQ_API_KEY")

        if not groq_api_key:
            raise CommandError(
                "GROQ_API_KEY is missing. Add it to your .env file."
            )

        llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name="openai/gpt-oss-120b",
            temperature=0.1,
            max_tokens=1024,
        )

        self.stdout.write(f"\nUser: {user.username}")
        self.stdout.write(f"Query: {QUERY}")
        self.stdout.write("=" * 70)
        self.stdout.write(
            f"Top K: {TOP_K} | Score threshold: {SCORE_THRESHOLD}"
        )

        # Run RAG pipeline
        try:
            result = rag_advanced(
                QUERY,
                retriever,
                llm,
                owner_id=user.id,
                top_k=TOP_K,
                min_score=SCORE_THRESHOLD,
                return_context=RETURN_CONTEXT,
            )
        except Exception as exc:
            raise CommandError(
                f"RAG pipeline failed: {exc}"
            ) from exc

        # Print generated answer
        self.stdout.write("\nANSWER")
        self.stdout.write("-" * 70)
        self.stdout.write(result["answer"])

        # Print retrieval confidence
        self.stdout.write("\nCONFIDENCE")
        self.stdout.write("-" * 70)
        self.stdout.write(
            f"{result['confidence']:.3f}"
        )

        # Print sources
        self.stdout.write("\nSOURCES")
        self.stdout.write("-" * 70)

        if not result["sources"]:
            self.stdout.write(
                "No sources passed the retrieval threshold."
            )
        else:
            for index, source in enumerate(
                result["sources"], start=1
            ):
                self.stdout.write(
                    f"\n[{index}] {source['source']} | "
                    f"Page {source['page']} | "
                    f"Similarity {source['score']:.3f}"
                )
                self.stdout.write(source["preview"])

        # Optionally print the full context
        if RETURN_CONTEXT:
            self.stdout.write("\nFULL CONTEXT")
            self.stdout.write("-" * 70)
            self.stdout.write(result["context"])
