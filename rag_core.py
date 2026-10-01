"""Shared local retrieval and Gemini generation functions."""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sentence_transformers import SentenceTransformer

from pdf_to_vector import EMBEDDING_MODEL, create_embeddings

DEFAULT_INDEX = "vector_index.pkl"
GEMINI_MODEL = "gemini-3.6-flash"
NOT_FOUND_MESSAGE = "I don't have enough information in the provided document."


def load_index(index_path: Path) -> Dict[str, Any]:
    """Load and validate a persisted FAISS index payload."""
    if not index_path.exists():
        raise FileNotFoundError(
            f"Index file not found: {index_path}. Run pdf_to_vector.py first."
        )
    with index_path.open("rb") as file:
        payload = pickle.load(file)
    required = {"index", "chunks", "pages", "embedding_model"}
    if not required.issubset(payload):
        raise ValueError("The index file is missing required metadata.")
    if payload["embedding_model"] != EMBEDDING_MODEL:
        raise ValueError("This index was created with an incompatible embedding model.")
    return payload


def retrieve(
    payload: Dict[str, Any], question: str, model: SentenceTransformer, k: int = 5
) -> List[Dict[str, Any]]:
    """Return top matches plus adjacent chunks to preserve local context."""
    query_vector = create_embeddings([question], model)
    _, indices = payload["index"].search(query_vector, min(k, payload["index"].ntotal))
    selected_indices = set()
    for chunk_index in indices[0]:
        if chunk_index < 0:
            continue
        index = int(chunk_index)
        selected_indices.update(range(max(0, index - 1), min(payload["index"].ntotal, index + 2)))

    sources: List[Dict[str, Any]] = []
    for index in sorted(selected_indices):
        sources.append(
            {"page": int(payload["pages"][index]), "text": payload["chunks"][index]}
        )
    return sources


def generate_answer(question: str, sources: List[Dict[str, Any]]) -> str:
    """Ask Gemini to answer from retrieved context, retrying once on failure."""
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")
    client = genai.Client(api_key=api_key)
    context = "\n\n---\n\n".join(
        f"Page {source['page']}:\n{source['text']}" for source in sources
    )
    prompt = (
        "You are a PDF question-answering assistant.\n\n"
        "Answer ONLY using the document context supplied below.\n"
        "Do not invent facts or use outside knowledge.\n"
        f'If the document does not contain the answer, respond exactly: "{NOT_FOUND_MESSAGE}".\n\n'
        "Document context:\n"
        f"{context}\n\n"
        f"User question:\n{question}\n\n"
        "Give a concise, clear answer. At the end, state the relevant PDF page number(s)."
    )
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            response = client.interactions.create(model=GEMINI_MODEL, input=prompt)
            answer = response.output_text.strip()
            if answer:
                return answer
            raise RuntimeError("Gemini returned an empty answer.")
        except Exception as error:
            last_error = error
            if attempt == 0 and _is_temporary_error(error):
                continue
            break
    raise RuntimeError(f"Gemini request failed after retry: {last_error}")


def _is_temporary_error(error: Exception) -> bool:
    """Return whether an API error is likely safe to retry once."""
    status_code = getattr(error, "status_code", None)
    if status_code in {408, 409, 429} or (isinstance(status_code, int) and status_code >= 500):
        return True
    message = str(error).lower()
    return any(marker in message for marker in ("timeout", "temporarily unavailable", "rate limit"))


def answer_question(
    payload: Dict[str, Any], question: str, model: SentenceTransformer
) -> Tuple[str, List[Dict[str, Any]]]:
    """Retrieve sources and generate a grounded answer."""
    sources = retrieve(payload, question, model)
    if not sources:
        return NOT_FOUND_MESSAGE, []
    return generate_answer(question, sources), sources