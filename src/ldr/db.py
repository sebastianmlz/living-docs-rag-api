from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from ldr.config import get_settings


@contextmanager
def connect(*, vector: bool = True, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    """Abre una conexión; hace commit al salir sin errores y rollback si hay excepción.

    `vector=True` registra el tipo `vector` para leer/escribir embeddings como arrays.
    Requiere que la extensión ya exista, por eso las migraciones usan `vector=False`.

    `autocommit=True`: cada `with conn.transaction()` es una transacción real que se confirma al salir.
    Sin autocommit, la primera consulta abre una transacción implícita y los `transaction()` de adentro
    son solo savepoints: nada queda guardado hasta cerrar la conexión.
    """
    with psycopg.connect(get_settings().database_url, autocommit=autocommit) as conn:
        if vector:
            register_vector(conn)
        yield conn
