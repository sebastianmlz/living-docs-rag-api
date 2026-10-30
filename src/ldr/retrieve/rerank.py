"""Reranking: un segundo modelo, más caro y más preciso, reordena los candidatos de la búsqueda."""

from dataclasses import replace
from functools import cached_property
from pathlib import Path
from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder

from ldr.retrieve.hit import Hit


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class FastembedReranker:
    """Cross-encoder local.

    El modelo de embeddings (bi-encoder) codifica pregunta y chunk POR SEPARADO: rápido, porque los
    vectores de los chunks se calculan una vez al indexar. El cross-encoder lee pregunta y chunk JUNTOS
    y decide qué tan relevante es uno para el otro: mucho más preciso, pero hay que correrlo por cada
    par en cada pregunta. Por eso solo se aplica a los ~20 candidatos, nunca a todo el corpus.
    """

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir

    @cached_property
    def _model(self) -> TextCrossEncoder:
        return TextCrossEncoder(self.model_name, cache_dir=str(self.cache_dir))

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        if not hits:
            return []
        scores = self._model.rerank(query, [f"{hit.section}\n\n{hit.content}" for hit in hits])
        scored = sorted(zip(scores, hits, strict=True), key=lambda pair: pair[0], reverse=True)
        return [replace(hit, score=float(score)) for score, hit in scored]
