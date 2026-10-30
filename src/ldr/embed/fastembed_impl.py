from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from tokenizers import Tokenizer


@dataclass(frozen=True)
class ModelSpec:
    dim: int
    # Modelos asimétricos: la pregunta y el documento se embeben con instrucciones distintas.
    # fastembed no las agrega; sin ellas el modelo rinde peor.
    document_template: str
    query_template: str


# Agregar un modelo = agregar su spec aquí + una migración con su índice HNSW parcial.
MODELS = {
    "google/embeddinggemma-300m": ModelSpec(
        dim=768,
        document_template="title: {title} | text: {text}",
        query_template="task: search result | query: {text}",
    ),
}


class FastembedEmbedder:
    """Embeddings locales con ONNX Runtime: sin API key, sin límites de rate, en CPU."""

    def __init__(self, model_name: str, cache_dir: Path, batch_size: int = 16) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.spec = MODELS[model_name]
        self.dim = self.spec.dim
        self.batch_size = batch_size

    @cached_property
    def _model(self) -> TextEmbedding:
        # Se carga recién al primer uso: una corrida sin cambios no paga los segundos de carga.
        # La primera vez descarga el modelo a la caché de Hugging Face.
        return TextEmbedding(self.model_name, cache_dir=str(self.cache_dir))

    @cached_property
    def _tokenizer(self) -> Tokenizer:
        # El tokenizer del propio modelo (atributo interno de fastembed): los chunks se miden en la misma
        # unidad en la que el modelo trunca.
        return self._model.model.tokenizer

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def embed_documents(self, items: list[tuple[str, str]]) -> list[np.ndarray]:
        texts = [self.spec.document_template.format(title=t or "none", text=x) for t, x in items]
        return list(self._model.embed(texts, batch_size=self.batch_size))

    def embed_query(self, query: str) -> np.ndarray:
        return next(iter(self._model.embed([self.spec.query_template.format(text=query)])))
