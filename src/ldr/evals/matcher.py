"""El puente entre la búsqueda y las métricas: ¿qué evidencias del golden set cubre cada chunk?

Criterio (5.2): un chunk cubre una evidencia si viene de la MISMA página y contiene el fragmento
textual (comparado con `normalize`, que ignora formato y espacios). Funciona igual para los dos
chunkers porque no depende de secciones ni anclas.

Límite conocido: si un chunk corta el fragmento por la mitad (el recursivo corta por tamaño), ese
chunk no lo cubre aunque tenga casi todo. `unreachable_units` mide cuántas evidencias quedan así:
es el techo de recall de cada estrategia, y conviene saberlo antes de culpar al buscador.
"""

from collections.abc import Iterable

from ldr.evals.golden import GoldenItem, contains
from ldr.retrieve.hit import Hit


def covered_units(path: str, content: str, item: GoldenItem) -> frozenset[str]:
    """Las unidades de `item` (q007#e1, ...) que cubre un chunk de `path` con `content`."""
    return frozenset(
        f"{item.id}#e{n}"
        for n, ev in enumerate(item.evidence, start=1)
        if ev.path == path and contains(content, ev.quote)
    )


def to_ranking(hits: Iterable[Hit], item: GoldenItem) -> list[frozenset[str]]:
    """El formato que esperan las métricas: por cada hit, en orden, las unidades que cubre."""
    return [covered_units(hit.path, hit.content, item) for hit in hits]


def unreachable_units(chunks: Iterable[tuple[str, str]], items: Iterable[GoldenItem]) -> list[str]:
    """Unidades que NINGÚN chunk de la estrategia contiene completas: ninguna búsqueda puede acertarlas.

    `chunks`: (path, content) de todos los chunks de una estrategia.
    """
    by_path: dict[str, list[str]] = {}
    for path, content in chunks:
        by_path.setdefault(path, []).append(content)
    missing = []
    for item in items:
        for n, ev in enumerate(item.evidence, start=1):
            if not any(contains(content, ev.quote) for content in by_path.get(ev.path, [])):
                missing.append(f"{item.id}#e{n}")
    return missing
