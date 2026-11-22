"""El golden set: preguntas con su respuesta esperada y la EVIDENCIA que debe recuperarse.

Criterio de relevancia (decidido en la 5.2): cada evidencia es una página de la documentación más un
fragmento copiado TEXTUAL de ella. Un chunk es relevante para esa evidencia si viene de esa página y
contiene el fragmento. Así sirve igual para los dos chunkers, aunque el recursivo no sepa de secciones.

Cada evidencia es una "unidad relevante" para las métricas de `metrics.py`, con id `q007#e1`.
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Kind = Literal["single", "multi", "unanswerable"]
Lang = Literal["es", "en"]

_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # [texto](url) -> texto
_FORMATTING = re.compile(r"[*`]")  # negritas, cursivas y código en línea
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lo que se compara al buscar un fragmento dentro de un chunk.

    El LLM que genera el golden set copia el texto "como se lee": suele quitar los ** de una negrita o
    los ` de un nombre de código, y los saltos de línea no le importan. Si se comparara byte a byte,
    un fragmento bien copiado fallaría por formato. Ojo: el _ NO se quita, en código significa algo
    (response_model).
    """
    text = _LINK.sub(r"\1", text)
    text = _FORMATTING.sub("", text)
    return _SPACES.sub(" ", text).strip().casefold()


def contains(haystack: str, quote: str) -> bool:
    return normalize(quote) in normalize(haystack)


class Evidence(BaseModel):
    path: str  # tutorial/query-params.md, igual que documents.path en la BD
    section: str  # "Query Parameters > Defaults": solo para que una persona lo revise
    quote: str  # textual del documento


class GoldenItem(BaseModel):
    id: str  # q001
    question: str
    lang: Lang
    kind: Kind
    evidence: list[Evidence]  # vacía en las no respondibles
    reference_answer: str | None  # para medir correctness; None en las no respondibles

    def unit_ids(self) -> set[str]:
        """Las unidades relevantes de esta pregunta, en el formato que esperan las métricas."""
        return {f"{self.id}#e{n}" for n in range(1, len(self.evidence) + 1)}


def save(items: list[GoldenItem], path: Path) -> None:
    """JSONL: una pregunta por línea. Se lee y se compara en un diff sin abrir nada especial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in items), encoding="utf-8", newline="\n"
    )


def append(item: GoldenItem, path: Path) -> None:
    """Agrega UNA pregunta al final y la deja en disco al instante: si el proceso muere, lo hecho queda."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(item.model_dump_json() + "\n")


def load(path: Path) -> list[GoldenItem]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenItem.model_validate_json(line) for line in lines if line.strip()]
