"""Búsqueda léxica (full-text search de Postgres): los chunks que contienen las palabras de la pregunta."""

import psycopg

from ldr.retrieve.hit import HIT_COLUMNS, Hit

# plainto_tsquery normaliza la pregunta (minúsculas, sin stopwords, raíces: "parameters" → 'paramet')
# pero une los términos con AND (&): una pregunta larga casi nunca aparece COMPLETA en un chunk.
# Cambiando & por | (OR) alcanza con que aparezcan algunas; ts_rank_cd premia a los chunks que tienen
# más términos y más cerca entre sí. NULLIF: una pregunta solo de stopwords no busca nada.
_QUERY = f"""
    WITH q AS (
        SELECT NULLIF(replace(plainto_tsquery('english', %(query)s)::text, '&', '|'), '')::tsquery AS tsq
    )
    SELECT {HIT_COLUMNS}, ts_rank_cd(c.tsv, q.tsq) AS score
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    CROSS JOIN q
    WHERE c.tsv @@ q.tsq AND c.strategy = %(strategy)s AND d.deleted_at IS NULL
    ORDER BY score DESC
    LIMIT %(k)s
"""  # noqa: S608 - HIT_COLUMNS es una constante del código; los valores van como parámetros


def lexical_search(
    conn: psycopg.Connection, query: str, *, strategy: str, k: int = 20
) -> list[Hit]:
    rows = conn.execute(_QUERY, {"query": query, "strategy": strategy, "k": k}).fetchall()
    return [Hit.from_row(row) for row in rows]
