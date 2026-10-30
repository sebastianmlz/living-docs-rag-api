"""Búsqueda semántica: los chunks cuyo vector está más cerca del de la pregunta."""

import numpy as np
import psycopg
from psycopg import sql

from ldr.retrieve.hit import HIT_COLUMNS, Hit


def vector_search(
    conn: psycopg.Connection,
    query_vector: np.ndarray,
    *,
    model: str,
    dim: int,
    strategy: str,
    k: int = 20,
    ef_search: int = 100,
) -> list[Hit]:
    """Top-k por distancia coseno (`<=>`), usando el índice HNSW parcial del modelo.

    Para que Postgres use ese índice, la consulta tiene que repetir su forma exacta:
      - el mismo cast `embedding::vector(768)`, y
      - el filtro `model = '...'` como LITERAL: con un parámetro, el planificador no puede probar que la
        consulta cae dentro del índice parcial.
    La dimensión y el modelo vienen de nuestra configuración, no del usuario; aun así se componen con
    `psycopg.sql` (que escapa) y nunca con f-strings.
    """
    vector_type = sql.SQL("vector({})").format(sql.Literal(dim))
    distance = sql.SQL("e.embedding::{t} <=> %(q)s::{t}").format(t=vector_type)
    query = sql.SQL(
        """
        WITH nearest AS MATERIALIZED (
            SELECT {columns}, {distance} AS distance
            FROM chunk_embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE e.model = {model} AND c.strategy = %(strategy)s AND d.deleted_at IS NULL
            ORDER BY {distance}
            LIMIT %(k)s
        )
        SELECT id, path, title, url, anchor, heading_path, content, 1 - distance
        FROM nearest
        ORDER BY distance
        """
    ).format(columns=sql.SQL(HIT_COLUMNS), distance=distance, model=sql.Literal(model))

    with conn.transaction():
        # HNSW es aproximado: explora ~ef_search candidatos y DESPUÉS aplica los filtros (strategy, borrados).
        # Si muchos candidatos no pasan el filtro, devolvería menos de k. El iterative scan (pgvector 0.8)
        # sigue explorando el grafo hasta juntar k filas válidas; relaxed_order puede desordenar un poco,
        # por eso el CTE materializado y el ORDER BY final.
        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        conn.execute(sql.SQL("SET LOCAL hnsw.ef_search = {}").format(sql.Literal(ef_search)))
        rows = conn.execute(query, {"q": query_vector, "strategy": strategy, "k": k}).fetchall()
    return [Hit.from_row(row) for row in rows]
