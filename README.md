# Free PDF RAG with Gemini, FAISS, and FastAPI

This final-year project answers questions about a PDF using Retrieval-Augmented Generation (RAG):

1. `pypdf` extracts text.
2. Text is split into overlapping 500-character chunks within each original PDF page.
3. `all-MiniLM-L6-v2` creates 384-dimensional embeddings locally. No embedding API is used.
4. FAISS retrieves the five closest chunks plus their adjacent chunks.
5. Gemini answers using only those retrieved chunks.

## Cost

- `sentence-transformers` embeddings: free and local.
- FAISS storage: free and local.
- Embedding a 100-page book: ₹0.
- Gemini: free tier, subject to Google's current quotas. The commonly advertised limit is 15 requests/minute, but limits can change by account, region, and model. Check Google AI Studio for the current quota.
- Gemini generation uses the Interactions API with `gemini-3.6-flash`.

Never commit `.env` or expose an API key in `.env.example`.

## 1. Get a free Gemini API key

1. Open [Google AI Studio](https://aistudio.google.com/).
2. Sign in with a Google account.
3. Select **Get API key**.
4. Create or select a Google Cloud project.
5. Copy the key. It normally starts with `AIza`.

## 2. Install

From this project folder in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip uninstall -y google-generativeai
python -m pip install --upgrade google-genai
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder:

```env
GEMINI_API_KEY=AIza_your_real_key_here
```

If your old `.env` contains another provider key, replace it with `GEMINI_API_KEY`. Revoke any API key that was accidentally placed in a shared file.

## 3. Build the index

Put your PDF beside the scripts as `input.pdf`, or pass an absolute path:

```powershell
python pdf_to_vector.py input.pdf
python pdf_to_vector.py "C:\path\to\your\document.pdf"
```

The script prints `Processing page X...`, creates page-aware chunks, downloads the embedding model the first time, and writes `vector_index.pkl`. A scanned image-only PDF needs OCR before it can be indexed. Rebuild the index after changing the chunking code.

## 4. Use the CLI

```powershell
python query_gemini.py
```

Ask a question, then type `quit` or `exit`. The answer includes the retrieved page sources. `query_vector.py` remains as a backward-compatible alias for the Gemini CLI.

## 5. Run the FastAPI server

```powershell
python -m uvicorn main:app --reload
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`.

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Question request:

```powershell
curl -X POST http://127.0.0.1:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"What is the main topic of the document?"}'
```

The same request in PowerShell is:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask `
  -ContentType "application/json" `
  -Body '{"question":"What is the main topic of the document?"}'
```

The response has this shape:

```json
{
  "answer": "...",
  "sources": [
    {"page": 2, "text": "retrieved document text"}
  ]
}
```

Set a different index with `VECTOR_INDEX_PATH`:

```powershell
$env:VECTOR_INDEX_PATH = "sample_index.pkl"
python -m uvicorn main:app --reload
```

## 6. Run tests

The tests create a temporary two-page PDF, verify 384-dimensional embeddings and FAISS retrieval, mock Gemini for a deterministic answer, and check `/health` plus validation behavior.

```powershell
pytest -q test_api.py
```

The first test run downloads `all-MiniLM-L6-v2` from Hugging Face. This is a one-time local download and does not require a paid API.

## Project files

- `pdf_to_vector.py`: PDF extraction, chunking, local embeddings, and FAISS persistence.
- `rag_core.py`: shared index loading, retrieval, Gemini prompt, and retry logic.
- `query_gemini.py`: interactive CLI.
- `main.py`: `/health` and `/ask` FastAPI endpoints with CORS.
- `test_api.py`: local PDF and API tests.
- `sample_questions.txt`: ten questions for demonstrations.

## Troubleshooting

### API key not working

Confirm `.env` contains `GEMINI_API_KEY`, the key starts with `AIza`, and there are no extra quotes or spaces. Confirm the key is enabled for the Gemini API in Google AI Studio.

If you see a `404 model is not found` error, confirm that `gemini-3.6-flash` is available to your API key and restart the server or CLI.

### Rate limit exceeded

Wait about one minute and try again. Free quotas are shared and can change. The application retries one failed Gemini request, but it does not bypass quota limits.

### Module not found

Activate the virtual environment and run:

```powershell
python -m pip install -r requirements.txt
```

### Index file not found

Run `python pdf_to_vector.py input.pdf` first, or set `VECTOR_INDEX_PATH` to the location of an existing `.pkl` file.

### Empty or irrelevant answers

The PDF may be scanned, have very little extractable text, or not contain the requested information. Run indexing again after OCR, and remember that the model is instructed not to invent information outside the retrieved context.

## Deployment notes

For Hugging Face Spaces, choose a Docker or Python Space, copy the project files, add `GEMINI_API_KEY` under Space Secrets, build the index during deployment or store the generated index as an artifact, and expose the Uvicorn port expected by the Space. A free Render service can run the same application with a start command such as `uvicorn main:app --host 0.0.0.0 --port $PORT`; check the provider's current free-tier policy before relying on it. Do not use Railway without verifying its current pricing.

For a quick frontend, a Streamlit app can send a POST request to `/ask` and display `answer` plus each source page. Keep the API key on the server, never in browser code.

## Demo screenshots

Add project screenshots here after your local demo:

<!-- Screenshot placeholder: CLI question and grounded answer -->
<!-- Screenshot placeholder: FastAPI /docs page -->
<!-- Screenshot placeholder: frontend response with source pages -->
