"""python -m ldr.retrieve "pregunta": compara los modos de búsqueda lado a lado."""

import argparse

from ldr.config import get_settings
from ldr.db import connect
from ldr.embed.fastembed_impl import FastembedEmbedder
from ldr.ingest.chunkers import STRATEGIES
from ldr.retrieve.rerank import FastembedReranker
from ldr.retrieve.retriever import MODES, Retriever


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Búsqueda vectorial, léxica e híbrida sobre el corpus"
    )
    parser.add_argument("query")
    parser.add_argument("--strategy", choices=list(STRATEGIES), default="markdown")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--rerank", action="store_true", help="reordena con el cross-encoder")
    args = parser.parse_args()

    settings = get_settings()
    retriever = Retriever(
        FastembedEmbedder(settings.embedding_model, settings.models_dir),
        strategy=args.strategy,
        reranker=FastembedReranker(settings.reranker_model, settings.models_dir)
        if args.rerank
        else None,
    )
    with connect() as conn:
        for mode in MODES:
            print(f"\n=== {mode}{' + rerank' if args.rerank else ''} ({args.strategy}) ===")
            hits = retriever.search(conn, args.query, mode=mode, k=args.k)
            if not hits:
                print("  (sin resultados)")
            for rank, hit in enumerate(hits, start=1):
                preview = " ".join(hit.content.split())[:110]
                print(
                    f"{rank}. [{hit.score:.4f}] {hit.section}\n   {hit.citation_url}\n   {preview}"
                )


if __name__ == "__main__":
    main()
