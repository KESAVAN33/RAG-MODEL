"""Interactive CLI for asking questions about a saved PDF index."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from pdf_to_vector import EMBEDDING_MODEL
from rag_core import answer_question, load_index


def main() -> int:
    """Run the interactive question loop."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="vector_index.pkl")
    args = parser.parse_args()
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY is missing. Add it to your .env file.", file=sys.stderr)
        return 1
    try:
        print("Loading index...")
        payload = load_index(Path(args.index))
        model = SentenceTransformer(EMBEDDING_MODEL)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Ask questions about the PDF. Type 'quit' or 'exit' to stop.")
    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            print("Please enter a non-empty question.")
            continue
        try:
            print("Searching for relevant sections...")
            answer, sources = answer_question(payload, question, model)
            pages = sorted({source["page"] for source in sources})
            print(f"\nAnswer:\n{answer}")
            print(f"Found relevant info on pages: {', '.join(map(str, pages)) or 'none'}")
        except Exception as error:
            print(f"Error while answering question: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())