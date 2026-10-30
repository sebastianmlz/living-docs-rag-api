from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Delta:
    """Un pedazo de la respuesta en streaming. El último trae `usage` (los tokens que se cobran)."""

    text: str = ""
    usage: Usage | None = None


class LLMUnavailableError(Exception):
    """El proveedor no respondió después de los reintentos (límite de cuota, caída, key inválida)."""


class LLMClient(Protocol):
    """Lo que la app necesita de un LLM. Gemini hoy; cambiar de proveedor es otra clase con este método."""

    model: str

    def stream(self, system: str, user: str) -> Iterator[Delta]: ...
