from conftest import make_doc

from ldr.ingest.pipeline import ingest

QUERY_DOC = make_doc(
    "tutorial/query-params.md",
    "# Query Parameters { #query-parameters }\n\n"
    + "Function parameters that are not path parameters are query parameters. " * 10
    + "\n\n## Optional parameters { #optional-parameters }\n\n"
    + "Set the default to None to make a query parameter optional. " * 10,
)
ERRORS_DOC = make_doc(
    "tutorial/handling-errors.md",
    "# Handling Errors\n\n"
    + "Raise HTTPException to return an HTTP error response to the client. " * 5,
)


def test_second_run_without_changes_does_nothing(conn, embedder) -> None:
    first = ingest(conn, [QUERY_DOC, ERRORS_DOC], embedder, ["markdown", "recursive"])
    second = ingest(conn, [QUERY_DOC, ERRORS_DOC], embedder, ["markdown", "recursive"])

    assert (first.new, first.embedded) == (2, first.embedded) and first.embedded > 0
    assert (second.unchanged, second.new, second.updated, second.embedded) == (2, 0, 0, 0)


def test_changed_document_reuses_vectors_of_identical_chunks(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC], embedder, ["markdown"])
    changed = make_doc(
        QUERY_DOC.path, QUERY_DOC.text + "\n\n## New section\n\n" + "Brand new text here. " * 30
    )
    stats = ingest(conn, [changed], embedder, ["markdown"])

    assert stats.updated == 1
    assert stats.reused >= 1  # las secciones que no cambiaron no se vuelven a embeber
    assert stats.embedded >= 1  # la sección nueva sí
    version = conn.execute(
        "SELECT version FROM documents WHERE path = %s", (QUERY_DOC.path,)
    ).fetchone()
    assert version == (2,)


def test_missing_document_is_tombstoned(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC, ERRORS_DOC], embedder, ["markdown"])
    stats = ingest(conn, [QUERY_DOC], embedder, ["markdown"])

    assert stats.deleted == 1
    row = conn.execute(
        "SELECT deleted_at IS NOT NULL, (SELECT count(*) FROM chunks c WHERE c.document_id = d.id) "
        "FROM documents d WHERE path = %s",
        (ERRORS_DOC.path,),
    ).fetchone()
    assert row == (True, 0)  # la fila queda (historia), sus chunks no


def test_partial_run_does_not_tombstone(conn, embedder) -> None:
    ingest(conn, [QUERY_DOC, ERRORS_DOC], embedder, ["markdown"])
    stats = ingest(conn, [QUERY_DOC], embedder, ["markdown"], prune=False)

    assert stats.deleted == 0
