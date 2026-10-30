"""Aplica en orden los archivos de db/migrations que todavía no se han ejecutado."""

from pathlib import Path

import psycopg

from ldr.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    """Devuelve los nombres de las migraciones aplicadas en esta llamada."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

    done = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.stem in applied:
            continue
        # Cada migración es atómica: o se aplica completa o no se aplica.
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
        done.append(path.name)
    return done


def main() -> None:
    # autocommit: cada migración se confirma por separado; si la 3 falla, la 1 y la 2 quedan aplicadas.
    with connect(vector=False, autocommit=True) as conn:
        for name in apply_migrations(conn):
            print(f"applied {name}")
    print("migrations up to date")


if __name__ == "__main__":
    main()
