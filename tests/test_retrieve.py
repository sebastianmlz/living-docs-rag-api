from conftest import make_doc
from test_pipeline import ERRORS_DOC, QUERY_DOC

from ldr.ingest.pipeline import ingest
from ldr.retrieve.hit import Hit
from ldr.retrieve.hybrid import reciprocal_rank_fusion
from ldr.retrieve.lexical import lexical_search
from ldr.retrieve.retriever import Retriever

ROUTING_DOC = make_doc(
    "tutorial/bigger-applications.md",
    "# Bigger Applications\n\n"
    + "Use APIRouter to split routes across several files and modules. " * 5,
)


def hit(chunk_id: int) -> Hit:
    return Hit(chunk_id, "p.md", "T", "https://x/", None, (), "text", 0.0)


def test_rrf_rewards_agreement_between_rankings() -> None:
    vector = [hit(1), hit(2), hit(3)]
    lexical = [hit(3), hit(1), hit(4)]
    fused = [h.chunk_id for h in reciprocal_rank_fusion([vector, lexical])]

    # 1 y 3 aparecen en las dos listas; 1 está más arriba en promedio (1º y 2º contra 3º y 1º).
    assert fused[:2] == [1, 3]
    assert set(fused) == {1, 2, 3, 4}


def test_vector_search_finds_the_relevant_section(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC, ERRORS_DOC, ROUTING_DOC], embedder, ["markdown"])
    hits = Retriever(embedder).search(
        conn, "make a query parameter optional with None", mode="vector"
    )

    assert hits[0].path == QUERY_DOC.path
    assert hits[0].citation_url.endswith("#optional-parameters")


def test_lexical_search_matches_exact_identifiers(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC, ERRORS_DOC, ROUTING_DOC], embedder, ["markdown"])
    hits = lexical_search(conn, "how do I use HTTPException?", strategy="markdown")

    assert hits[0].path == ERRORS_DOC.path


def test_lexical_search_with_only_stopwords_returns_nothing(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC], embedder, ["markdown"])

    assert lexical_search(conn, "the of and", strategy="markdown") == []


def test_search_filters_strategy_and_deleted_documents(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC, ERRORS_DOC, ROUTING_DOC], embedder, ["markdown", "recursive"])
    ingest(
        conn, [QUERY_DOC, ROUTING_DOC], embedder, ["markdown", "recursive"]
    )  # ERRORS_DOC se borra
    hits = Retriever(embedder, strategy="recursive", candidates=50).search(
        conn, "HTTPException error", mode="hybrid", k=50
    )

    assert hits
    assert ERRORS_DOC.path not in {h.path for h in hits}
    strategies = conn.execute(
        "SELECT DISTINCT strategy FROM chunks WHERE id = ANY(%s)", ([h.chunk_id for h in hits],)
    ).fetchall()
    assert strategies == [("recursive",)]
