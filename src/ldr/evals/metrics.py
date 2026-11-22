"""Métricas de recuperación.

Todas reciben un *ranking* ya traducido a unidades relevantes: para cada resultado de la búsqueda, en
orden, el id de la unidad relevante que cubre o `None` si no cubre ninguna. Una unidad es una evidencia
del golden set (página + fragmento textual, ver `golden.py`), con id como "q007#e1". Quién decide si
un chunk cubre una unidad es otro módulo (`matcher.py`); aquí no se sabe nada de chunks, de la BD ni
de estrategias: es matemática pura y se prueba con listas.

Una posición puede cubrir VARIAS unidades (un chunk que contiene dos evidencias), así que cada
elemento del ranking puede ser un id, un conjunto de ids o `None`.

Ejemplo: la búsqueda devolvió [A, S, B, C, D] y solo S es relevante  ->  ranking = [None, "S", None, None, None]

Detalle importante: varias posiciones pueden cubrir la MISMA unidad (dos trozos de la misma sección).
Recall y nDCG cuentan cada unidad una sola vez; precision sí cuenta cada chunk, porque mide cuánto del
prompt es útil.
"""

import math
from collections.abc import Iterable, Sequence
from statistics import fmean

Entry = str | frozenset[str] | set[str] | None
Ranking = Sequence[Entry]


def _units(entry: Entry) -> set[str]:
    if entry is None:
        return set()
    if isinstance(entry, str):
        return {entry}
    return set(entry)


def _check(relevant: set[str], k: int | None = None) -> None:
    if not relevant:
        # Una pregunta sin respuesta en el corpus no tiene recall definido (0/0). Esas preguntas
        # sirven para calibrar el umbral de relevancia, no para estas métricas.
        raise ValueError("la pregunta no tiene unidades relevantes")
    if k is not None and k < 1:
        raise ValueError(f"k debe ser >= 1, no {k}")


def recall_at_k(ranking: Ranking, relevant: set[str], k: int) -> float:
    """Qué fracción de lo relevante apareció en el top k.

    Es la métrica principal de un RAG: el LLM solo ve el top k; lo que no está ahí, no existe.
    """
    _check(relevant, k)
    found = set().union(*(_units(e) for e in ranking[:k])) & relevant
    return len(found) / len(relevant)


def precision_at_k(ranking: Ranking, relevant: set[str], k: int) -> float:
    """Qué fracción de los k resultados es útil (el resto es ruido que gasta tokens en el prompt).

    Se divide por k aunque la búsqueda haya devuelto menos resultados: devolver poco no es mérito.
    """
    _check(relevant, k)
    useful = sum(1 for e in ranking[:k] if _units(e) & relevant)
    return useful / k


def reciprocal_rank(ranking: Ranking, relevant: set[str]) -> float:
    """1 / posición del primer resultado relevante (0 si no aparece ninguno).

    Promediado sobre todas las preguntas es el MRR (Mean Reciprocal Rank). Premia que lo primero
    correcto esté bien arriba: posición 1 -> 1.0, posición 2 -> 0.5, posición 4 -> 0.25.
    """
    _check(relevant)
    for position, entry in enumerate(ranking, start=1):
        if _units(entry) & relevant:
            return 1 / position
    return 0.0


def _discount(position: int) -> float:
    # Cuánto vale un acierto según su posición: 1.0, 0.63, 0.5, 0.43, 0.39...
    return 1 / math.log2(position + 1)


def ndcg_at_k(ranking: Ranking, relevant: set[str], k: int) -> float:
    """Calidad del ORDEN del top k, entre 0 y 1 (Normalized Discounted Cumulative Gain).

    DCG: cada unidad relevante suma 1 / log2(posición + 1), solo la primera vez que aparece.
    IDCG: el DCG del ranking ideal (una unidad relevante por posición, todas primero). nDCG = DCG / IDCG.
    Si un chunk trae dos unidades a la vez, el DCG puede pasar al ideal "una por posición": eso ya es
    un orden perfecto, así que se topa en 1.
    """
    _check(relevant, k)
    seen: set[str] = set()
    dcg = 0.0
    for position, entry in enumerate(ranking[:k], start=1):
        new = (_units(entry) & relevant) - seen
        seen |= new
        dcg += len(new) * _discount(position)
    ideal = sum(_discount(position) for position in range(1, min(len(relevant), k) + 1))
    return min(dcg / ideal, 1.0)


def score_query(
    ranking: Ranking, relevant: set[str], ks: Iterable[int] = (1, 3, 5)
) -> dict[str, float]:
    """Todas las métricas de una pregunta, con nombres listos para una tabla: recall@5, mrr, ..."""
    scores = {"mrr": reciprocal_rank(ranking, relevant)}
    for k in ks:
        scores[f"recall@{k}"] = recall_at_k(ranking, relevant, k)
        scores[f"precision@{k}"] = precision_at_k(ranking, relevant, k)
        scores[f"ndcg@{k}"] = ndcg_at_k(ranking, relevant, k)
    return scores


def mean_scores(per_query: Sequence[dict[str, float]]) -> dict[str, float]:
    """Promedio de cada métrica sobre todas las preguntas (así el reciprocal rank pasa a ser MRR)."""
    if not per_query:
        raise ValueError("no hay preguntas que promediar")
    return {name: fmean(scores[name] for scores in per_query) for name in per_query[0]}
