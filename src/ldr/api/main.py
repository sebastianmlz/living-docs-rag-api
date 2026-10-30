import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from ldr.config import get_settings
from ldr.db import connect
from ldr.embed.base import Embedder
from ldr.embed.fastembed_impl import FastembedEmbedder
from ldr.generate.answer import answer_events
from ldr.generate.gemini_client import GeminiClient
from ldr.generate.llm import LLMClient
from ldr.retrieve.rerank import FastembedReranker, Reranker
from ldr.retrieve.retriever import Mode, Retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@dataclass
class Services:
    """Lo caro de crear (modelos, cliente del LLM) se crea UNA vez al arrancar, no en cada request."""

    embedder: Embedder
    reranker: Reranker | None
    llm: LLMClient | None  # None si no hay GEMINI_API_KEY: /ask responde 503 en vez de romperse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    services = Services(
        embedder=FastembedEmbedder(settings.embedding_model, settings.models_dir),
        reranker=FastembedReranker(settings.reranker_model, settings.models_dir),
        llm=GeminiClient(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
        if settings.gemini_api_key
        else None,
    )
    if settings.warmup_models:
        # Carga los modelos ahora (unos segundos al arrancar) para que la primera pregunta no los pague:
        # sin esto, la búsqueda tardaba ~3 s en la primera pregunta y ~50 ms en las siguientes.
        services.embedder.embed_query("warmup")
    app.state.services = services
    yield


app = FastAPI(title="living-docs-rag", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_db() -> Iterator[psycopg.Connection]:
    with connect() as conn:
        yield conn


def get_services(request: Request) -> Services:
    return request.app.state.services


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    mode: Mode = "hybrid"
    strategy: str = Field(default="markdown", pattern="^(markdown|recursive)$")
    k: int = Field(default=5, ge=1, le=10)
    rerank: bool = False


Db = Annotated[psycopg.Connection, Depends(get_db)]


@app.get("/health")
def health(conn: Db) -> dict[str, str]:
    """Comprueba que la API responde, que hay conexión a la BD y que pgvector está instalado."""
    row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    return {"status": "ok", "pgvector": row[0] if row else "missing"}


@app.post("/ask")
def ask(
    body: AskRequest,
    conn: Db,
    services: Annotated[Services, Depends(get_services)],
) -> EventSourceResponse:
    """Responde en streaming (Server-Sent Events): eventos `sources`, `delta`*, y `done` o `error`.

    La búsqueda se hace ANTES de empezar a transmitir: así la conexión a la BD se libera al terminar el
    request, y el stream solo depende del LLM.
    """
    if services.llm is None:
        raise HTTPException(503, "GEMINI_API_KEY no está configurada")
    retriever = Retriever(
        services.embedder,
        strategy=body.strategy,
        reranker=services.reranker if body.rerank else None,
    )
    start = time.perf_counter()
    hits = retriever.search(conn, body.question, mode=body.mode, k=body.k)
    retrieval_ms = (time.perf_counter() - start) * 1000
    return EventSourceResponse(answer_events(services.llm, body.question, hits, retrieval_ms))
