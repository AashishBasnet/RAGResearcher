"""Retrieval + generation for the chat. Yields small event dicts so callers can stream them."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from .retriever import get_retriever

load_dotenv()

NO_CONTEXT_ANSWER = "No relevant context found in the uploaded papers."

PROMPT = """You are ResearchQA, an assistant that answers questions using the supplied research-paper excerpts.

Instructions:
- Answer using only information supported by the context.
- If the context does not sufficiently answer the question, say: "I couldn't find sufficient information to answer this question in the uploaded research papers."
- If the question is unrelated to the context, do not answer it using general knowledge.
- Be concise, clear, and factual.
- Do not invent citations or unsupported claims.
- Each excerpt starts with a header naming its paper and page. Cite as (Paper title, p. 6). Never refer to excerpts by number.
- Check the question's own assumptions against the context. If the question assumes something the context does not state, or contradicts it, say so plainly and give what the context actually says instead of explaining the assumption.
- Do not explain mechanisms that the excerpts do not state. If the context does not spell out the reason, say it is not covered.
- Write math in plain text, for example m_χ = 0.1 m_H. Do not use LaTeX.

Context:
{context}

Question:
{query}

Answer:
"""


@lru_cache(maxsize=1)
def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")
    return ChatGroq(
        groq_api_key=api_key,
        model_name="openai/gpt-oss-120b",
        temperature=0.1,
        max_tokens=1024,
    )


def _title(metadata):
    return metadata.get("paper_title") or metadata.get("source_file") or "Unknown paper"


def _page_info(metadata):
    """Return (1-based page number for links, label for display)."""
    index = metadata.get("page")
    number = index + 1 if isinstance(index, int) else None
    label = metadata.get("page_label") or number
    return number, label


def build_sources(results):
    """One entry per (paper, page), keeping the best score."""
    best = {}
    for doc in results:
        metadata = doc.get("metadata", {})
        number, label = _page_info(metadata)
        key = (metadata.get("paper_id"), number)
        score = doc.get("similarity_score", 0.0)
        if key not in best or score > best[key]["score"]:
            best[key] = {
                "paper_id": metadata.get("paper_id"),
                "title": _title(metadata),
                "page": label,
                "page_number": number,
                "score": round(score, 3),
            }
    return sorted(best.values(), key=lambda s: s["score"], reverse=True)


def build_context(results):
    """Prefix each excerpt with a header so the model can cite title and page."""
    blocks = []
    for i, doc in enumerate(results, start=1):
        metadata = doc.get("metadata", {})
        _, label = _page_info(metadata)
        blocks.append(f'[Excerpt {i} from "{_title(metadata)}", page {label}]\n{doc["content"]}')
    return "\n\n".join(blocks)

CONDENSE_PROMPT = """Given the conversation below and a follow-up question, rewrite the follow-up as a single standalone question that can be understood without the conversation. Keep all technical terms. If the follow-up is already standalone, return it unchanged. Only replace references such as "that" or "the lighter case" with what they refer to. Do not add facts or conclusions from the Assistant's earlier answers, which may be wrong. Return only the question, nothing else.

Conversation:
{history}

Follow-up question: {question}

Standalone question:"""


def _format_history(history, max_chars=500):
    lines = []
    for message in history:
        role = "User" if message["role"] == "user" else "Assistant"
        lines.append(f"{role}: {message['content'][:max_chars]}")
    return "\n".join(lines)


def condense_question(question, history):
    """Turn a follow-up into a standalone search question. No history means no extra LLM call."""
    if not history:
        return question
    prompt = CONDENSE_PROMPT.format(history=_format_history(history), question=question)
    response = get_llm().invoke(prompt)
    rewritten = (response.content if hasattr(response, "content") else str(response)).strip()
    return rewritten or question

def stream_rag_answer(query, owner_id, history=None, top_k=8, min_score=0.35):
    search_query = condense_question(query, history or [])
    yield {"type": "query", "text": search_query}

    results = get_retriever().retrieve(
        search_query, owner_id=owner_id, top_k=top_k, score_threshold=min_score
    )

    if not results:
        yield {"type": "sources", "sources": [], "confidence": 0.0}
        yield {"type": "token", "text": NO_CONTEXT_ANSWER}
        return

    confidence = max(doc.get("similarity_score", 0.0) for doc in results)
    yield {"type": "sources", "sources": build_sources(results), "confidence": confidence}

    prompt = PROMPT.format(context=build_context(results), query=search_query)
    for chunk in get_llm().stream(prompt):
        text = chunk.content if hasattr(chunk, "content") else str(chunk)
        if text:
            yield {"type": "token", "text": text}