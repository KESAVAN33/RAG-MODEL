"""FastAPI backend for the local-embedding Gemini RAG application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from pdf_to_vector import EMBEDDING_MODEL
from rag_core import answer_question, load_index

load_dotenv()

app = FastAPI(title="Free PDF RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    """Request body for a document question."""

    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    """Response body containing the answer and retrieved sources."""

    answer: str
    sources: List[Dict[str, Any]]


def get_resources() -> tuple[Dict[str, Any], SentenceTransformer]:
    """Load the persisted index and local embedding model for one request."""
    index_path = Path(os.getenv("VECTOR_INDEX_PATH", "vector_index.pkl"))
    payload = load_index(index_path)
    model = SentenceTransformer(EMBEDDING_MODEL)
    return payload, model


@app.get("/health")
def health() -> Dict[str, str]:
    """Return a simple liveness response."""
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: QuestionRequest) -> AskResponse:
    """Answer a question using the retrieved PDF context."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    try:
        payload, model = get_resources()
        answer, sources = answer_question(payload, question, model)
        return AskResponse(answer=answer, sources=sources)
    except FileNotFoundError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"RAG request failed: {error}") from error