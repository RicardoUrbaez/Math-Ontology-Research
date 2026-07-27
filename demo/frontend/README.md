# MathOntoSpeak Professor Paper Demo

This local React/Vite app demonstrates the post-meeting research direction: analyze a paper context and explain selected equations with ontology-backed semantic speech instead of raw notation-only reading.

## Run

Start the FastAPI server from the repository root:

```powershell
python -m uvicorn api.main:app --reload
```

Start the frontend from this folder:

```powershell
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`.

## Demo Workflow

1. Paste a paper title and abstract/context, or upload a PDF for lightweight text extraction.
2. Enter one LaTeX equation per line, or clear the equation box and use extraction from pasted math delimiters.
3. Choose the audience mode and optional backend audio artifact setting.
4. Click **Analyze paper**.
5. Inspect raw LaTeX, plain notation reading, MathOntoSpeak semantic reading, contextual explanation, resolved ontology concepts, linked text span, and audio/ASR evidence notes.

Browser speech synthesis powers the **Play semantic reading** button. Backend audio artifact generation is optional and remains safe when Azure credentials are not configured.
