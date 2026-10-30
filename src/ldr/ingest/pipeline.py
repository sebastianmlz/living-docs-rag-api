"""Carga incremental: solo se reprocesa lo que cambió, y se reutilizan los vectores de los chunks idénticos."""

import hashlib
from dataclasses import dataclass

import numpy as np
import psycopg

from ldr.embed.base import Embedder
from ldr.ingest.chunkers import STRATEGIES
from ldr.ingest.loader import Document


@dataclass
class IngestStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    chunks: int = 0
    embedded: int = 0  # vectores calculados
    reused: int = 0  # vectores copiados de un chunk idéntico anterior


def ingest(
    conn: psycopg.Connection,
    documents: list[Document],
    embedder: Embedder,
    strategies: list[str],
    *,
    source: str = "fastapi-docs",
    prune: bool = True,
    force: bool = False,
) -> IngestStats:
    """`prune`: marcar como borrados los documentos que ya no están (solo si `documents` es el corpus completo).
    `force`: reprocesar aunque el hash no haya cambiado (p. ej. al agregar una estrategia)."""
    stats = IngestStats()
    known = {
        path: (doc_id, content_hash, deleted)
        for doc_id, path, content_hash, deleted in conn.execute(
            "SELECT id, path, content_hash, deleted_at IS NOT NULL FROM documents WHERE source = %s",
            (source,),
        )
    }

    for doc in documents:
        previous = known.get(doc.path)
        if previous and previous[1] == doc.content_hash and not previous[2] and not force:
            stats.unchanged += 1
            continue
        # Un documento por transacción: si la corrida se corta, lo ya procesado queda guardado.
        with conn.transaction():
            doc_id = _upsert_document(conn, source, doc)
            _replace_chunks(conn, doc_id, doc, embedder, strategies, stats)
        if previous:
            stats.updated += 1
        else:
            stats.new += 1
        print(f"  {'upd' if previous else 'new'} {doc.path}")

    if prune:
        present = {doc.path for doc in documents}
        gone = [
            doc_id
            for path, (doc_id, _h, deleted) in known.items()
            if path not in present and not deleted
        ]
        if gone:
            with conn.transaction():
                conn.execute("DELETE FROM chunks WHERE document_id = ANY(%s)", (gone,))
                conn.execute("UPDATE documents SET deleted_at = now() WHERE id = ANY(%s)", (gone,))
            stats.deleted = len(gone)
    return stats


def _upsert_document(conn: psycopg.Connection, source: str, doc: Document) -> int:
    # En el SET, `documents.x` es el valor viejo: la versión sube solo si el hash cambió.
    row = conn.execute(
        """
        INSERT INTO documents (source, path, title, url, content_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source, path) DO UPDATE SET
            title        = EXCLUDED.title,
            url          = EXCLUDED.url,
            version      = documents.version
                           + (documents.content_hash IS DISTINCT FROM EXCLUDED.content_hash)::int,
            content_hash = EXCLUDED.content_hash,
            updated_at   = now(),
            deleted_at   = NULL
        RETURNING id
        """,
        (source, doc.path, doc.title, doc.url, doc.content_hash),
    ).fetchone()
    assert row is not None  # noqa: S101 - RETURNING siempre devuelve la fila
    return row[0]


def _replace_chunks(
    conn: psycopg.Connection,
    doc_id: int,
    doc: Document,
    embedder: Embedder,
    strategies: list[str],
    stats: IngestStats,
) -> None:
    # Vectores de los chunks actuales, por hash: si un párrafo no cambió, su vector tampoco.
    reusable: dict[str, np.ndarray] = dict(
        conn.execute(
            """
            SELECT c.chunk_hash, e.embedding
            FROM chunks c JOIN chunk_embeddings e ON e.chunk_id = c.id
            WHERE c.document_id = %s AND e.model = %s
            """,
            (doc_id, embedder.model_name),
        ).fetchall()
    )
    conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))

    # hash -> (título, texto, ids de los chunks con ese texto); el mismo texto en dos estrategias se embebe una vez.
    pending: dict[str, tuple[str, str, list[int]]] = {}
    for name in strategies:
        for chunk in STRATEGIES[name](doc.text, embedder.count_tokens):
            title = " > ".join(chunk.heading_path) or doc.title
            chunk_hash = hashlib.sha256(f"{title}\n{chunk.content}".encode()).hexdigest()
            row = conn.execute(
                """
                INSERT INTO chunks (document_id, strategy, ordinal, heading_path, anchor, content,
                                    token_count, chunk_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    doc_id,
                    name,
                    chunk.ordinal,
                    list(chunk.heading_path),
                    chunk.anchor,
                    chunk.content,
                    chunk.token_count,
                    chunk_hash,
                ),
            ).fetchone()
            assert row is not None  # noqa: S101
            stats.chunks += 1
            if chunk_hash in reusable:
                _store_embeddings(conn, embedder.model_name, [row[0]], reusable[chunk_hash])
                stats.reused += 1
            else:
                pending.setdefault(chunk_hash, (title, chunk.content, []))[2].append(row[0])

    if pending:
        items = list(pending.values())
        vectors = embedder.embed_documents([(title, text) for title, text, _ids in items])
        for (_title, _text, ids), vector in zip(items, vectors, strict=True):
            _store_embeddings(conn, embedder.model_name, ids, vector)
        stats.embedded += len(items)


def _store_embeddings(
    conn: psycopg.Connection, model: str, chunk_ids: list[int], vector: np.ndarray
) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunk_embeddings (chunk_id, model, embedding) VALUES (%s, %s, %s)",
            [(chunk_id, model, vector) for chunk_id in chunk_ids],
        )
