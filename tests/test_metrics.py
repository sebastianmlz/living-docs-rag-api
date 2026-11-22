import math

import pytest

from ldr.evals.metrics import (
    mean_scores,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    score_query,
)

# El ejemplo de la explicación: la búsqueda devuelve [A, S, B, C, D] y solo S es relevante.
EXAMPLE = [None, "S", None, None, None]
ONLY_S = {"S"}


def test_worked_example() -> None:
    assert recall_at_k(EXAMPLE, ONLY_S, 5) == 1.0
    assert reciprocal_rank(EXAMPLE, ONLY_S) == 0.5
    assert precision_at_k(EXAMPLE, ONLY_S, 5) == pytest.approx(0.2)
    assert ndcg_at_k(EXAMPLE, ONLY_S, 5) == pytest.approx(1 / math.log2(3))  # 0.63


def test_k_cuts_the_ranking() -> None:
    # S está en la posición 2: con k=1 no se ve.
    assert recall_at_k(EXAMPLE, ONLY_S, 1) == 0.0
    assert ndcg_at_k(EXAMPLE, ONLY_S, 1) == 0.0


def test_recall_counts_units_not_chunks() -> None:
    relevant = {"S1", "S2"}

    assert recall_at_k(["S1", "S1", None], relevant, 3) == 0.5  # dos chunks de S1 no cuentan doble
    assert recall_at_k(["S2", None, "S1"], relevant, 3) == 1.0


def test_precision_counts_chunks() -> None:
    # Dos chunks de la misma sección: los dos son útiles en el prompt.
    assert precision_at_k(["S", "S", None, None], ONLY_S, 4) == 0.5


def test_precision_divides_by_k_even_with_fewer_results() -> None:
    assert precision_at_k(["S"], ONLY_S, 5) == pytest.approx(0.2)


def test_ndcg_rewards_order() -> None:
    relevant = {"S1", "S2"}

    perfect = ndcg_at_k(["S1", "S2", None], relevant, 3)
    late = ndcg_at_k([None, "S1", "S2"], relevant, 3)

    assert perfect == pytest.approx(1.0)
    assert 0 < late < perfect


def test_ndcg_never_exceeds_one_with_duplicates() -> None:
    assert ndcg_at_k(["S", "S", "S"], ONLY_S, 3) == pytest.approx(1.0)


def test_nothing_found() -> None:
    assert reciprocal_rank([None, None], ONLY_S) == 0.0
    assert recall_at_k([], ONLY_S, 5) == 0.0
    assert ndcg_at_k([], ONLY_S, 5) == 0.0


def test_unanswerable_question_has_no_retrieval_metrics() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["S"], set(), 5)


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError):
        precision_at_k(EXAMPLE, ONLY_S, 0)


def test_score_query_and_mean() -> None:
    first = score_query(EXAMPLE, ONLY_S, ks=(1, 5))  # S en posición 2
    second = score_query(["S"], ONLY_S, ks=(1, 5))  # S en posición 1

    assert set(first) == {
        "mrr",
        "recall@1",
        "precision@1",
        "ndcg@1",
        "recall@5",
        "precision@5",
        "ndcg@5",
    }
    mean = mean_scores([first, second])
    assert mean["mrr"] == pytest.approx(0.75)  # (0.5 + 1.0) / 2
    assert mean["recall@1"] == pytest.approx(0.5)
    assert mean["recall@5"] == pytest.approx(1.0)


def test_one_chunk_can_cover_two_units() -> None:
    # Las dos evidencias de una pregunta quedaron en el MISMO chunk: con ese chunk ya está todo.
    ranking = [{"e1", "e2"}, None, None]
    both = {"e1", "e2"}
    assert recall_at_k(ranking, both, 1) == 1.0
    assert precision_at_k(ranking, both, 1) == 1.0  # un chunk útil, no dos
    assert reciprocal_rank(ranking, both) == 1.0
    assert ndcg_at_k(ranking, both, 3) == 1.0  # topado: es el mejor orden posible


def test_a_set_entry_only_counts_units_not_seen_before() -> None:
    ranking = ["e1", {"e1", "e2"}]
    # e1 ya contó en la posición 1; la 2 solo aporta e2: igual que el ranking ideal ["e1", "e2"].
    assert ndcg_at_k(ranking, {"e1", "e2"}, 2) == pytest.approx(1.0)
    assert recall_at_k(["e1", set()], {"e1", "e2"}, 2) == 0.5
