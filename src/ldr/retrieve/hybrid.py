"""Búsqueda híbrida: combina rankings con Reciprocal Rank Fusion (RRF)."""

from dataclasses import replace

from ldr.retrieve.hit import Hit


def reciprocal_rank_fusion(rankings: list[list[Hit]], k: int = 60) -> list[Hit]:
    """puntaje(chunk) = Σ 1 / (k + posición en cada ranking donde aparece).

    No se pueden sumar los puntajes originales: la similitud coseno va de -1 a 1 y ts_rank_cd no tiene
    techo. RRF solo mira la POSICIÓN, así que no necesita normalizar nada. Un chunk que sale arriba en
    las dos listas gana; uno que sale solo en una, pero primero, también puntúa alto.
    `k` = 60 es el valor del paper original: amortigua la diferencia entre el puesto 1 y el 2.
    """
    scores: dict[int, float] = {}
    first_seen: dict[int, Hit] = {}
    for ranking in rankings:
        for position, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + position)
            first_seen.setdefault(hit.chunk_id, hit)
    ordered = sorted(scores, key=scores.__getitem__, reverse=True)
    return [replace(first_seen[chunk_id], score=scores[chunk_id]) for chunk_id in ordered]
