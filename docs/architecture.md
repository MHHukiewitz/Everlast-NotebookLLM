# Architecture

See the interview plan. Runtime shape:

- `apps/web` — three-column UI
- `apps/api` — FastAPI, skills, RAG, research
- `infra/docker-compose.yml` — Postgres, Redis, Ollama, SearXNG, Langfuse, api, worker, web

The chat agent loads a short skill list, then the full schema of the chosen skill. MCP is not the primary path.

Studio reads `GET /api/skills`. Notes, Mindmap, Report, Quiz, Flashcards, and Table are available. Locked skills return HTTP 400. Add a later feature as one registry entry plus a renderer. Each artifact can export md, csv, pdf, json, or mermaid.
