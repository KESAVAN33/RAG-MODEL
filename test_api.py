"""Small offline tests for indexing, retrieval, and FastAPI endpoints."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sentence_transformers import SentenceTransformer

from main import app
from pdf_to_vector import EMBEDDING_MODEL, build_index
from rag_core import answer_question, load_index


def create_test_pdf(path: Path) -> None:
    """Create a simple two-page PDF for local testing."""
    document = canvas.Canvas(str(path))
    document.drawString(72, 720, "Page one discusses Python and retrieval augmented generation.")
    document.showPage()
    document.drawString(72, 720, "Page two discusses FAISS vector search and Gemini.")
    document.save()


def test_index_and_query() -> None:
    """Verify local embeddings and a mocked non-empty answer."""
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        pdf_path = folder / "test.pdf"
        index_path = folder / "vector_index.pkl"
        create_test_pdf(pdf_path)
        build_index(pdf_path, index_path)
        payload = load_index(index_path)
        model = SentenceTransformer(EMBEDDING_MODEL)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("rag_core.generate_answer", return_value="Test answer"):
                answer, sources = answer_question(payload, "What does page two discuss?", model)
        assert answer == "Test answer"
        assert sources
        assert payload["index"].d == 384


def test_fastapi_health() -> None:
    """Verify the liveness endpoint."""
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fastapi_rejects_empty_question() -> None:
    """Verify that blank questions are rejected."""
    response = TestClient(app).post("/ask", json={"question": "   "})
    assert response.status_code in {400, 422}


if __name__ == "__main__":
    test_index_and_query()
    test_fastapi_health()
    test_fastapi_rejects_empty_question()
    print("All local tests passed.")