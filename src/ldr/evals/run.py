"""Corre el golden set contra cada configuración del retriever y guarda las métricas.

python -m ldr.evals.run   (o: poe evals)      requiere Postgres arriba (poe up) y el corpus ingerido

Matriz: 2 chunkers × 3 modos (vector, léxica, híbrida) × con/sin reranker = 12 configuraciones.
Cada configuración responde las 60 preguntas con el top k que vería el LLM. Las respondibles dan
recall/precision/MRR/nDCG; las no respondibles solo guardan el puntaje del primer resultado, que es
lo que se usará para calibrar el umbral.

El resultado queda en evals/results/<fecha>.json con el hash del golden set usado: dos corridas solo
son comparables si midieron con el mismo examen. El archivo se reescribe al terminar CADA
configuración ("complete": false mientras falten), así que si la corrida se corta (las del reranker
tardan unos 20 min cada una) se conserva lo ya medido.
"""

import argparse
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean, median

import numpy as np
import psycopg

from ldr.embed.base import Embedder
from ldr.evals.golden import GoldenItem, load
from ldr.evals.matcher import to_ranking, unreachable_units
from ldr.evals.metrics import mean_scores, score_query
from ldr.ingest.chunkers import STRATEGIES
from ldr.retrieve.rerank import Reranker
from ldr.retrieve.retriever import MODES, Mode, Retriever

K = 5  # lo que entra al prompt


@dataclass(frozen=True)
class Config:
    strategy: str
    mode: Mode
    rerank: bool

    @property
    def name(self) -> str:
        return f"{self.strategy}·{self.mode}{'·rerank' if self.rerank else ''}"


CONFIGS = [Config(s, m, r) for s in STRATEGIES for m in MODES for r in (False, True)]


class CachedQueryEmbedder:
    """Envuelve al embedder para calcular el vector de cada pregunta UNA vez (no 6 veces).

    Ojo: por eso la latencia medida no incluye el embedding de la pregunta (se mide aparte).
    """

    def __init__(self, inner: Embedder) -> None:
        self.inner = inner
        self.model_name = inner.model_name
        self.dim = inner.dim
        self._cache: dict[str, np.ndarray] = {}

    def count_tokens(self, text: str) -> int:
        return self.inner.count_tokens(text)

    def embed_documents(self, items: list[tuple[str, str]]) -> list[np.ndarray]:
        return self.inner.embed_documents(items)

    def embed_query(self, query: str) -> np.ndarray:
        if query not in self._cache:
            self._cache[query] = self.inner.embed_query(query)
        return self._cache[query]


def run_config(
    conn: psycopg.Connection, retriever: Retriever, config: Config, items: list[GoldenItem]
) -> dict:
    """Las 60 preguntas con una configuración: el detalle por pregunta y los promedios."""
    questions = []
    latencies = []
    for item in items:
        start = time.perf_counter()
        hits = retriever.search(conn, item.question, mode=config.mode, k=K)
        latencies.append((time.perf_counter() - start) * 1000)
        row: dict = {
            "id": item.id,
            "kind": item.kind,
            "lang": item.lang,
            "top_score": hits[0].score if hits else None,
            "hits": [{"path": h.path, "chunk_id": h.chunk_id, "score": h.score} for h in hits],
        }
        if item.evidence:
            ranking = to_ranking(hits, item)
            row["scores"] = score_query(ranking, item.unit_ids())
            for h, units in zip(row["hits"], ranking, strict=True):
                h["units"] = sorted(units)
        questions.append(row)
    return {
        "questions": questions,
        "summary": summarize(questions),
        "latency_ms": latency(latencies),
    }


def summarize(questions: list[dict]) -> dict:
    """Promedios sobre las respondibles: en total, por idioma y por tipo (single/multi)."""
    scored = [q for q in questions if "scores" in q]
    groups: dict[str, list[dict]] = defaultdict(list)
    for q in scored:
        groups[f"lang={q['lang']}"].append(q["scores"])
        groups[f"kind={q['kind']}"].append(q["scores"])
    return {
        "all": mean_scores([q["scores"] for q in scored]),
        **{name: mean_scores(rows) for name, rows in sorted(groups.items())},
        "n": len(scored),
    }


def latency(values: list[float]) -> dict:
    return {"mean": round(fmean(values), 1), "p50": round(median(values), 1)}


def golden_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def save(payload: dict, out: Path) -> None:
    """Escribe el JSON de forma atómica: primero a un .tmp y después lo renombra encima.

    Si el proceso muere a mitad de la escritura, queda el archivo anterior entero (nunca uno a
    medias que no se puede leer). Termina en salto de línea y usa \n también en Windows, como
    esperan los hooks de pre-commit y git.
    """
    tmp = out.with_suffix(".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(out)


def print_table(results: list[dict]) -> None:
    cols = ["recall@5", "mrr", "ndcg@5", "precision@5"]
    header = f"{'configuración':<28}" + "".join(f"{c:>12}" for c in cols)
    header += f"{'recall@5 es':>13}{'recall@5 en':>13}{'multi r@5':>11}{'ms p50':>9}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda r: r["summary"]["all"]["recall@5"], reverse=True):
        s = r["summary"]
        line = f"{r['config']['name']:<28}" + "".join(f"{s['all'][c]:>12.3f}" for c in cols)
        line += f"{s['lang=es']['recall@5']:>13.3f}{s['lang=en']['recall@5']:>13.3f}"
        line += f"{s['kind=multi']['recall@5']:>11.3f}{r['latency_ms']['p50']:>9.0f}"
        print(line)


def main() -> None:
    from ldr.config import get_settings
    from ldr.db import connect
    from ldr.embed.fastembed_impl import FastembedEmbedder
    from ldr.retrieve.rerank import FastembedReranker

    parser = argparse.ArgumentParser(description="Mide el retriever con el golden set")
    parser.add_argument("--golden", type=Path, default=Path("evals/golden/golden.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--only", help="solo las configuraciones cuyo nombre contenga esto")
    args = parser.parse_args()

    settings = get_settings()
    items = load(args.golden)
    configs = [c for c in CONFIGS if not args.only or args.only in c.name]
    print(f"{len(items)} preguntas · {len(configs)} configuraciones · golden {args.golden}")

    embedder = CachedQueryEmbedder(FastembedEmbedder(settings.embedding_model, settings.models_dir))
    start = time.perf_counter()
    for item in items:  # el embedding de cada pregunta, una vez y medido aparte
        embedder.embed_query(item.question)
    embed_ms = (time.perf_counter() - start) * 1000 / len(items)
    reranker: Reranker | None = None
    if any(c.rerank for c in configs):
        reranker = FastembedReranker(settings.reranker_model, settings.models_dir)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now()
    out = args.out_dir / f"{created:%Y%m%d-%H%M%S}.json"
    results: list[dict] = []
    payload = {
        "created": created.isoformat(timespec="seconds"),
        "complete": False,
        "golden": {"path": args.golden.as_posix(), "sha256": golden_hash(args.golden)},
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "k": K,
        "candidates": Retriever(embedder).candidates,
        "embed_query_ms": round(embed_ms, 1),
        "unreachable_units": {},
        "results": results,  # la misma lista que se va llenando abajo
    }

    with connect() as conn:
        for strategy in STRATEGIES:
            rows = conn.execute(
                "SELECT d.path, c.content FROM chunks c JOIN documents d ON d.id = c.document_id "
                "WHERE c.strategy = %s AND d.deleted_at IS NULL",
                (strategy,),
            ).fetchall()
            missing = unreachable_units(rows, items)
            payload["unreachable_units"][strategy] = missing
            print(f"{strategy}: {len(missing)} evidencias inalcanzables")
        print(f"Guardando en {out} a medida que termina cada configuración")

        for config in configs:
            retriever = Retriever(
                embedder,
                strategy=config.strategy,
                reranker=reranker if config.rerank else None,
            )
            start = time.perf_counter()
            result = run_config(conn, retriever, config, items)
            print(f"  {config.name}: {time.perf_counter() - start:.0f}s")
            results.append({"config": {**asdict(config), "name": config.name}, **result})
            save(payload, out)

    payload["complete"] = True
    save(payload, out)

    print()
    print_table(results)
    print(
        f"\n(ms sin el embedding de la pregunta, que cuesta {embed_ms:.0f} ms y se calculó una vez)"
    )
    print(f"Resultados en {out}")


if __name__ == "__main__":
    main()
