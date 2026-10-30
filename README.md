# living-docs-rag-api

A retrieval-augmented question answering API over the [FastAPI documentation](https://fastapi.tiangolo.com/), built piece by piece without an orchestration framework so every step is visible: how documents are chunked, how the index stays in sync with a source that keeps changing, how search results are ranked, and what the model actually receives.

Ask in Spanish or English and get a streamed answer that cites the exact documentation section it came from.

> Work in progress. Ingestion, search and generation work end to end; evaluation, the web frontend and deployment are next.

## How it works

```
offline   docs (.md + code examples) → loader → chunkers → embeddings → Postgres + pgvector
online    question → vector + full-text search → RRF (→ rerank) → prompt → Gemini → SSE stream
```

- **Incremental ingestion.** Each page is hashed after its code examples are inlined. Unchanged pages are skipped, chunks whose text did not change keep their vectors, and pages removed upstream are tombstoned instead of deleted.
- **Two chunking strategies side by side.** A recursive splitter (baseline) and a markdown-aware one that cuts on headings, never splits code blocks and keeps the section anchor for citations. Both are stored so they can be compared.
- **Local embeddings.** `google/embeddinggemma-300m` through fastembed (ONNX, CPU). It is multilingual, so Spanish questions find English docs.
- **Search.** Cosine search on a partial HNSW index per embedding model, Postgres full-text search, reciprocal rank fusion of both, and an optional cross-encoder reranker (`bge-reranker-v2-m3`).
- **Generation.** Gemini answers only from the retrieved sources and cites them as `[n]`. Sources are treated as data, not instructions. Rate limits, 5xx errors and timeouts are retried with backoff.
- **Streaming API.** `POST /ask` returns server-sent events: `sources`, then `delta` chunks, then `done` with latency and token counts.

## Stack

Python 3.12 · uv · FastAPI · PostgreSQL 16 + pgvector · psycopg 3 · fastembed · Google Gen AI SDK · pytest · ruff · GitHub Actions

## Running it locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/) and a [Gemini API key](https://aistudio.google.com/).

```bash
cp .env.example .env            # then set GEMINI_API_KEY
uv sync
uv run poe up                   # Postgres + pgvector on localhost:5433
uv run poe migrate

# the corpus: FastAPI docs and their code examples only
git clone --depth 1 --filter=blob:none --sparse https://github.com/fastapi/fastapi.git data/fastapi
git -C data/fastapi sparse-checkout set docs/en/docs docs_src

uv run poe ingest               # first run downloads the embedding model (~1.2 GB)
uv run poe search "how do I make a query parameter optional?"
uv run poe api                  # http://127.0.0.1:8000/docs
```

Ask from the terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I add custom headers to an HTTPException?"}'
```

## Tasks

| Command | What it does |
|---|---|
| `uv run poe up` / `down` | Start / stop Postgres |
| `uv run poe migrate` | Apply pending SQL migrations |
| `uv run poe ingest` | Incremental ingestion (`--limit N`, `--force`) |
| `uv run poe search "..."` | Compare vector, full-text and hybrid search (`--rerank`, `--strategy recursive`) |
| `uv run poe api` | Development server |
| `uv run poe check` | Lint, format check and tests, same as CI |

## Tests

`uv run poe check` runs ruff and the test suite. Tests run against a separate `ldr_test` database inside a transaction that is always rolled back, and use small fakes for the embedding model and the LLM, so they need no network access and no model downloads.

## Project layout

```
src/ldr/
  ingest/     loader, markdown parsing, chunkers, incremental pipeline
  embed/      embedding model interface + fastembed implementation
  retrieve/   vector, full-text, hybrid (RRF), reranking
  generate/   prompt, Gemini client, streamed answer events
  api/        FastAPI app (/health, /ask)
db/migrations/  plain SQL migrations
tests/
```

## Roadmap

- [x] Incremental ingestion with two chunking strategies
- [x] Vector, full-text and hybrid search with reranking
- [x] Streamed answers with citations
- [ ] Evaluation: golden question set, recall@k / MRR / nDCG, LLM-as-judge
- [ ] Next.js frontend
- [ ] Deployment (Render + Neon) and scheduled re-ingestion
- [ ] Prompt-injection tests and evals in CI
