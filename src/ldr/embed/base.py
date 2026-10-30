from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Lo que el resto del sistema necesita de un modelo de embeddings, sin saber cuál es.

    Cambiar fastembed por Gemini (o por otro) es escribir otra clase con estos métodos; nada más cambia.
    """

    model_name: str
    dim: int

    def count_tokens(self, text: str) -> int: ...

    def embed_documents(self, items: list[tuple[str, str]]) -> list[np.ndarray]:
        """`items`: (título, texto). El título da contexto al fragmento (de qué página y sección viene)."""
        ...

    def embed_query(self, query: str) -> np.ndarray: ...
