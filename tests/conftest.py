import hashlib
import re
import zlib
from collections.abc import Iterator

import numpy as np
import psycopg
import pytest
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.conninfo import make_conninfo

from ldr.config import get_settings
from ldr.ingest.loader import Document, split_heading
from ldr.migrate import apply_migrations

TEST_DB = "ldr_test"


class FakeEmbedder:
    """Embeddings de juguete: cada palabra suma 1 en una posición fija del vector (bag of words).

    No entiende sinónimos, pero es determinista y no descarga nada: sirve para probar la LÓGICA de la
    búsqueda (SQL, filtros, fusión), no la calidad del modelo; eso lo miden los evals.
    """

    model_name = "test/bag-of-words"
    dim = 64

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def _vector(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for word in re.findall(r"[a-z]+", text.lower()):
            v[zlib.crc32(word.encode()) % self.dim] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def embed_documents(self, items: list[tuple[str, str]]) -> list[np.ndarray]:
        self.calls = getattr(self, "calls", 0) + len(items)
        return [self._vector(f"{title} {text}") for title, text in items]

    def embed_query(self, query: str) -> np.ndarray:
        return self._vector(query)


def make_doc(path: str, text: str) -> Document:
    title = split_heading(text.splitlines()[0].lstrip("# "))[0]
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return Document(
        path, title, f"https://example.test/{path.removesuffix('.md')}/", text, content_hash
    )


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Base `ldr_test` separada de la de desarrollo: se crea una vez y se migra al inicio de la sesión."""
    admin_url = get_settings().database_url
    with psycopg.connect(admin_url, autocommit=True) as admin:
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)
        ).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    url = make_conninfo(admin_url, dbname=TEST_DB)
    with psycopg.connect(url, autocommit=True) as conn:
        apply_migrations(conn)
    return url


@pytest.fixture
def conn(test_db_url: str) -> Iterator[psycopg.Connection]:
    """Cada test corre dentro de una transacción que SIEMPRE se deshace: la base queda limpia.

    Los `conn.transaction()` del código se vuelven savepoints dentro de esta transacción.
    """
    with psycopg.connect(test_db_url) as c:
        register_vector(c)
        with c.transaction(force_rollback=True):
            yield c


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()
