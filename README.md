# Dead Code Archaeologist

Dead Code Archaeologist mines a local git repository for functions that are likely dead code, enriches each suspect with git blame and commit history, and asks a local LLM (Mistral via Ollama) to return a structured verdict — **delete**, **investigate**, or **keep** — with a confidence score and rationale.

- `backend/` — FastAPI service: git mining, static analysis (Tree-sitter), call-graph building, LLM reasoning, disk-cached verdicts.
- `frontend/` — React + Vite client: streaming verdict dashboard, call-graph table, export to JSON/CSV.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.11 | 3.12+ recommended |
| Node.js | 18 | 20 LTS recommended |
| Git CLI | any recent | must be on `PATH` |
| Ollama | latest | see install steps below |

---

## 1 — Install Ollama

### macOS / Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download and run the installer from [https://ollama.com/download](https://ollama.com/download), then restart your terminal.

Verify the install:
```bash
ollama --version
```

---

## 2 — Pull the Mistral model

```bash
ollama pull mistral:7b-instruct-q4_K_M
```

The model is ~4 GB. Once downloaded it is cached locally and Ollama serves it automatically when the backend starts a request.

To confirm the model is available:
```bash
ollama list
```

---

## 3 — Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment variables (optional)

Create a `backend/.env` file to override defaults:

```env
# Ollama
LLM_MODEL=mistral:7b-instruct-q4_K_M
OLLAMA_BASE_URL=http://localhost:11434

# Evidence truncation (tune for your hardware)
MAX_SOURCE_LINES=80
MAX_BLAME_LINES=40
MAX_COMMITS=3
LLM_TIMEOUT=120
MAX_EVIDENCE_CHARS=6000
```

All variables have sensible defaults and the file is optional.

### Start the backend

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`.

---

## 4 — Frontend setup

```bash
cd frontend
npm install
```

### Environment variables (optional)

If your backend runs on a non-default URL, create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Start the dev server

```bash
npm run dev
```

The app opens at `http://localhost:5173`.

---

## 5 — Running the app

1. Make sure Ollama is running (`ollama serve` if it isn't already started as a service).
2. Start the backend (`uvicorn app.main:app --reload` from `backend/`).
3. Start the frontend (`npm run dev` from `frontend/`).
4. Open `http://localhost:5173`, enter the **absolute path** to any local git repository, and click **Analyze**.

Verdicts stream in via SSE as each function is judged. Results are cached in `.verdicts_cache/` inside the target repo so re-runs are instant.

---

## 6 — Running tests

```bash
cd backend
pytest
```

---

## Project structure

```text
backend/
  app/
    main.py              # FastAPI routes
    ast_parser.py        # Tree-sitter function + call extraction
    dead_code_detector.py# Call-graph builder and suspect finder
    git_explorer.py      # Commit history and blame via GitPython
    llm_agent.py         # Ollama/LangChain verdict agent
    cache.py             # Diskcache verdict persistence
    models.py            # Pydantic models
  tests/
  requirements.txt

frontend/
  src/
    pages/               # AnalyzePage, VerdictDetailPage, CallGraphPage
    components/          # SuspectRow, CallGraph, badges, etc.
    context/             # AnalysisContext (global state + SSE)
    services/            # api.js, export.js
  package.json
  vite.config.js
```
