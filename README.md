# Everlast Notebook

Source-grounded research notebook for the Everlast GmbH assignment. The app clones the Gemini Notebook layout (Quellen, Chat, Studio) without Google marks. Studio generators stay locked except notes.

## Stack

- Next.js UI (German)
- FastAPI, PostgreSQL + pgvector, Redis
- Ollama (default), Hetzner Inference (EU), EU OpenAI-compatible gateway, OpenRouter
- SearXNG, optional Langfuse

## Run (Compose)

```bash
cp .env.example .env
# set SESSION_SECRET, DEMO_EMAIL, DEMO_PASSWORD
# optional: REGISTER_ALLOWLIST=anna@everlast.de
# optional: OPENROUTER_API_KEY
docker compose -f infra/docker-compose.yml up --build
```

Send `DEMO_EMAIL` and `DEMO_PASSWORD` to the interviewer. Do not put the password on the login page. Registration accepts only emails in `REGISTER_ALLOWLIST`.

- UI: http://localhost:3000
- API: http://localhost:8000/docs
- Postgres (host): localhost:5433
- Langfuse: http://localhost:3001
- SearXNG: http://localhost:8080

Pull a local model once Ollama is up:

```bash
docker exec -it infra-ollama-1 ollama pull qwen2.5:7b
```

## Run (API + UI locally, Postgres in Docker)

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api && uvicorn app.main:app --reload --port 8000
cd apps/web && npm install && npm run dev
```

## Model routes

- **Lokal** — Ollama. Default. Data stays on the machine.
- **Hetzner** — set `HETZNER_API_KEY`. EU inference. Usually faster than local models.
- **EU** — set `EU_LLM_BASE_URL` and `EU_LLM_API_KEY`. Confirm the AVV notice.
- **OpenRouter** — set `OPENROUTER_API_KEY`. Confirm the transfer notice. Demo only.

Embeddings stay local. Default is Ollama `nomic-embed-text` (`EMBEDDING_BACKEND=ollama`). Pull it with `ollama pull nomic-embed-text`.

## Local Ollama

```bash
brew install ollama
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

Then chat in the notebook or run the eval harness:

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.eval --provider ollama --model qwen2.5:7b
```

Open http://localhost:3000/eval to review chat answers, HTML extract quality, the model-written source report, and Studio outputs (Mindmap, Report, Quiz). Score Treue, Nutzen, Zitate (1–5), pass/fail, and a comment. Start a second run with another model and use Vergleichen.

## MVP

Sources (file, text, URL), Fast/Deep research, grounded chat with citations, notes, skill registry, login, export/erase, AI Act labels, Impressum and Datenschutz. See [docs/compliance.md](docs/compliance.md).
