"""Punto de entrada de la recuperación: arma la búsqueda según la configuración del experimento."""

from dataclasses import dataclass
from typing import Literal

import psycopg

from ldr.embed.base import Embedder
from ldr.retrieve.hit import Hit
from ldr.retrieve.hybrid import reciprocal_rank_fusion
from ldr.retrieve.lexical import lexical_search
from ldr.retrieve.rerank import Reranker
from ldr.retrieve.vector import vector_search

Mode = Literal["vector", "lexical", "hybrid"]
MODES: tuple[Mode, ...] = ("vector", "lexical", "hybrid")


@dataclass
class Retriever:
    embedder: Embedder
    strategy: str = "markdown"
    candidates: int = 20  # cuántos trae cada búsqueda antes de fusionar / reordenar
    reranker: Reranker | None = None

    def search(
        self, conn: psycopg.Connection, query: str, *, mode: Mode = "hybrid", k: int = 5
    ) -> list[Hit]:
        rankings: list[list[Hit]] = []
        if mode in ("vector", "hybrid"):
            rankings.append(
                vector_search(
                    conn,
                    self.embedder.embed_query(query),
                    model=self.embedder.model_name,
                    dim=self.embedder.dim,
                    strategy=self.strategy,
                    k=self.candidates,
                )
            )
        if mode in ("lexical", "hybrid"):
            rankings.append(lexical_search(conn, query, strategy=self.strategy, k=self.candidates))

        hits = rankings[0] if len(rankings) == 1 else reciprocal_rank_fusion(rankings)
        if self.reranker:
            hits = self.reranker.rerank(query, hits[: self.candidates])
        return hits[:k]
