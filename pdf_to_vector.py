"""Extract a PDF, create local embeddings, and save a FAISS index."""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np
from dotenv import load_dotenv
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
OUTPUT_FILE = "vector_index.pkl"


def create_embeddings(texts: List[str], model: SentenceTransformer) -> np.ndarray:
    """Create 384-dimensional embeddings locally without an API call."""
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False).astype(
        "float32"
    )


def extract_pdf_pages(pdf_path: Path) -> List[str]:
    """Extract text page by page so chunk source pages remain exact."""
    reader = PdfReader(str(pdf_path))
    page_text = []
    for page_number, page in enumerate(reader.pages, start=1):
        print(f"Processing page {page_number}...")
        page_text.append(page.extract_text() or "")
    return page_text


def extract_pdf_text(pdf_path: Path) -> Tuple[str, int]:
    """Return all extracted text and the number of pages in a PDF."""
    page_text = extract_pdf_pages(pdf_path)
    return "\n".join(page_text).strip(), len(page_text)


def split_into_chunks(text: str, total_pages: int) -> Tuple[List[str], List[int]]:
    """Split text with overlap and estimate the source page for each chunk."""
    if not text or total_pages <= 0:
        return [], []

    chunks: List[str] = []
    pages: List[int] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    characters_per_page = max(1, len(text) // total_pages)

    for start in range(0, len(text), step):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if not chunk:
            continue
        chunks.append(chunk)
        page_number = min(start // characters_per_page + 1, total_pages)
        pages.append(page_number)

    return chunks, pages


def split_pages_into_chunks(page_text: List[str]) -> Tuple[List[str], List[int]]:
    """Create overlapping chunks independently within each original PDF page."""
    chunks: List[str] = []
    pages: List[int] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for page_number, text in enumerate(page_text, start=1):
        clean_text = text.strip()
        if not clean_text:
            continue
        for start in range(0, len(clean_text), step):
            chunk = clean_text[start : start + CHUNK_SIZE].strip()
            if chunk:
                chunks.append(chunk)
                pages.append(page_number)
    return chunks, pages


def build_index(pdf_path: Path, output_path: Path) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    page_text = extract_pdf_pages(pdf_path)
    text = "\n".join(page_text).strip()
    total_pages = len(page_text)
    if not text:
        raise ValueError("The PDF contains no extractable text.")

    chunks, pages = split_pages_into_chunks(page_text)
    if not chunks:
        raise ValueError("The PDF did not produce any text chunks.")

    print(f"Extracted {len(text):,} characters from {total_pages} page(s).")
    print(f"Created {len(chunks)} chunks.")
    print(f"Loading local embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    vectors = create_embeddings(chunks, model)
    print(f"Embedded {len(vectors)}/{len(chunks)} chunks locally.")
    if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION}-dimensional embeddings, got {vectors.shape}."
        )

    index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
    index.add(vectors)
    payload: Dict[str, Any] = {
        "index": index,
        "chunks": chunks,
        "pages": pages,
        "embedding_model": EMBEDDING_MODEL,
        "source_pdf": str(pdf_path),
    }

    with output_path.open("wb") as file:
        pickle.dump(payload, file)
    print(f"Index saved! {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", default="input.pdf", help="Path to the PDF")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Pickle output path")
    args = parser.parse_args()

    load_dotenv()
    try:
        build_index(Path(args.pdf), Path(args.output))
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
