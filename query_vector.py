"""Backward-compatible entry point for the Gemini CLI."""

from query_gemini import main


if __name__ == "__main__":
    raise SystemExit(main())
