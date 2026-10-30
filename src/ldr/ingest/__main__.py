"""python -m ldr.ingest: corre la ingesta incremental del corpus."""

import argparse
import time

from ldr.config import get_settings
from ldr.db import connect
from ldr.embed.fastembed_impl import FastembedEmbedder
from ldr.ingest.chunkers import STRATEGIES
from ldr.ingest.loader import load_documents
from ldr.ingest.pipeline import ingest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingesta incremental de la documentación de FastAPI"
    )
    parser.add_argument(
        "--limit", type=int, help="solo los primeros N archivos (prueba; no marca borrados)"
    )
    parser.add_argument(
        "--force", action="store_true", help="reprocesa aunque el hash no haya cambiado"
    )
    args = parser.parse_args()

    settings = get_settings()
    documents = load_documents(settings.corpus_dir)
    if args.limit:
        documents = documents[: args.limit]
    print(
        f"{len(documents)} documentos en {settings.corpus_dir} · modelo {settings.embedding_model}"
    )

    start = time.perf_counter()
    embedder = FastembedEmbedder(settings.embedding_model, settings.models_dir)
    # autocommit: cada documento se confirma al terminarlo; si la corrida se corta, lo hecho queda.
    with connect(autocommit=True) as conn:
        stats = ingest(
            conn, documents, embedder, list(STRATEGIES), prune=args.limit is None, force=args.force
        )
    print(f"{stats} en {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    main()
