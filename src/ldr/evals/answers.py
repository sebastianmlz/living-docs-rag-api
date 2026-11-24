"""Respuestas del sistema completo (búsqueda + LLM) para el golden set, y cuándo se abstiene.

python -m ldr.evals.answers   (o: poe answers)   requiere poe up, el corpus ingerido y GEMINI_API_KEY

Por qué existe (5.5): el puntaje de la búsqueda no separa las preguntas sin respuesta de las
respondibles (el mejor corte por puntaje acierta lo mismo que responder siempre). El que decide
"no sé" es el LLM, que sí lee las fuentes: el prompt le pide responder exactamente NO_ANSWER cuando
no alcanzan. Aquí se mide si lo hace bien:

- abstención correcta: de las preguntas sin respuesta, cuántas recibieron NO_ANSWER.
- abstención falsa: de las respondibles CON toda su evidencia en el contexto, cuántas recibieron
  NO_ANSWER aunque la respuesta estaba ahí. Si la búsqueda no trajo la evidencia, abstenerse es lo
  correcto y se cuenta aparte: ese error es del retriever, no del LLM.

Las respuestas quedan en una caché (.cache/evals/answers.jsonl) con clave = modelo + prompt completo.
Si nada cambió, no se vuelve a llamar a Gemini: así el juez de la 5.4 trabaja sobre estas mismas
respuestas y una corrida cortada sigue desde donde quedó con solo volver a lanzarla. Si cambia el
prompt, las fuentes recuperadas o el modelo, la clave cambia y se genera de nuevo.
"""

import argparse
import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from ldr.evals.golden import GoldenItem, load, normalize
from ldr.evals.matcher import to_ranking
from ldr.evals.metrics import recall_at_k
from ldr.generate.llm import LLMClient, LLMUnavailableError
from ldr.generate.prompts import NO_ANSWER, SYSTEM_PROMPT, build_user_message
from ldr.retrieve.hit import Hit

logger = logging.getLogger(__name__)

# Los defaults de /ask (src/ldr/api/main.py): se mide lo que recibe un usuario que no elige nada.
STRATEGY = "markdown"
MODE = "vector"
K = 5

Verdict = Literal["abstained", "mixed", "answered"]
Search = Callable[[str], list[Hit]]


@dataclass(frozen=True)
class Generated:
    """Una respuesta completa del LLM (sin streaming: aquí nadie la está mirando en vivo)."""

    text: str
    llm_called: bool
    llm_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def generate(llm: LLMClient, question: str, hits: list[Hit]) -> Generated:
    """Lo mismo que hace /ask (ver `answer_events`), juntando los pedazos en un solo texto."""
    if not hits:
        return Generated(
            NO_ANSWER, llm_called=False
        )  # igual que la API: sin contexto no hay llamada
    start = time.perf_counter()
    parts: list[str] = []
    usage = None
    for delta in llm.stream(SYSTEM_PROMPT, build_user_message(question, hits)):
        parts.append(delta.text)
        usage = delta.usage or usage
    return Generated(
        "".join(parts),
        llm_called=True,
        llm_ms=round((time.perf_counter() - start) * 1000),
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
    )


_QUOTES = "\"'“”«»"


def classify(text: str) -> Verdict:
    """¿El LLM se abstuvo?

    - abstained: respondió solo NO_ANSWER. Se toleran comillas, negritas y espacios alrededor,
      porque el prompt se la muestra entre comillas y el modelo a veces las copia.
    - mixed: respondió algo Y además dijo NO_ANSWER (por ejemplo, contesta a medias y dice que no
      encontró el resto). Se reporta aparte para revisarla a mano.
    - answered: no aparece NO_ANSWER. OJO: si el modelo tradujo la frase al inglés para una pregunta
      en inglés, cae aquí. Por eso el reporte lista las respuestas a las preguntas sin respuesta.
    """
    answer = normalize(text).strip(_QUOTES + " .")
    target = normalize(NO_ANSWER).strip(" .")
    if answer == target:
        return "abstained"
    return "mixed" if target in answer else "answered"


def cache_key(model: str, system: str, user: str) -> str:
    """Todo lo que determina la respuesta. El mensaje del usuario ya trae la pregunta y las fuentes."""
    payload = json.dumps([model, system, user], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


class AnswerCache:
    """JSONL de solo agregar: una respuesta por línea, escrita apenas llega (si el proceso muere,
    lo ya generado queda). Si una clave aparece dos veces, gana la última.

    Un Ctrl+C justo mientras escribe deja la última línea a medias: se descarta al leer (esa
    respuesta se vuelve a pedir) y se cierra con un salto de línea, para que la siguiente no quede
    pegada a ella y se pierda también."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, Generated] = {}
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("caché: línea incompleta descartada en %s", path)
                continue
            # En una sola línea fallaba: en `d[k] = v` Python evalúa v ANTES que k.
            key = row.pop("key")
            self._entries[key] = Generated(**row)
        if text and not text.endswith("\n"):
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write("\n")

    def get(self, key: str) -> Generated | None:
        return self._entries.get(key)

    def put(self, key: str, generated: Generated) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"key": key, **asdict(generated)}, ensure_ascii=False) + "\n")
        self._entries[key] = generated

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class Run:
    records: list[dict]
    llm_calls: int
    complete: bool  # False si Gemini se cayó a la mitad: volver a correr sigue desde la caché


def answer_all(
    items: Iterable[GoldenItem],
    search: Search,
    llm: LLMClient,
    cache: AnswerCache,
    *,
    delay_s: float = 0,
) -> Run:
    records: list[dict] = []
    calls = 0
    for item in items:
        hits = search(item.question)
        key = cache_key(llm.model, SYSTEM_PROMPT, build_user_message(item.question, hits))
        generated = cache.get(key)
        cached = generated is not None
        if generated is None:
            if calls and delay_s:
                time.sleep(delay_s)  # el free tier limita requests por minuto
            try:
                generated = generate(llm, item.question, hits)
            except LLMUnavailableError as exc:
                logger.error(
                    "Gemini no respondió en %s: %s. Lo hecho quedó en la caché.", item.id, exc
                )
                return Run(records, calls, complete=False)
            calls += generated.llm_called
            cache.put(key, generated)
        records.append(_record(item, hits, generated, cached=cached))
    return Run(records, calls, complete=True)


def _record(item: GoldenItem, hits: list[Hit], generated: Generated, *, cached: bool) -> dict:
    row: dict = {
        "id": item.id,
        "kind": item.kind,
        "lang": item.lang,
        "question": item.question,
        "answer": generated.text,
        "verdict": classify(generated.text),
        "hits": [{"path": h.path, "chunk_id": h.chunk_id, "score": h.score} for h in hits],
        "llm_ms": generated.llm_ms,
        "input_tokens": generated.input_tokens,
        "output_tokens": generated.output_tokens,
        "cached": cached,
    }
    if item.evidence:
        # Con qué contexto respondió: sin la evidencia en el top k, abstenerse es lo correcto.
        row["recall@5"] = recall_at_k(to_ranking(hits, item), item.unit_ids(), K)
    return row


def _counts(rows: list[dict]) -> dict:
    out: dict = {"n": len(rows)}
    for verdict in ("abstained", "mixed", "answered"):
        out[verdict] = sum(r["verdict"] == verdict for r in rows)
    out["abstention_rate"] = round(out["abstained"] / len(rows), 3) if rows else None
    return out


def summarize(records: list[dict]) -> dict:
    """Las dos tasas que importan, y su desglose por idioma y por contexto recuperado."""
    unanswerable = [r for r in records if r["kind"] == "unanswerable"]
    answerable = [r for r in records if r["kind"] != "unanswerable"]
    full = [r for r in answerable if r["recall@5"] == 1.0]
    partial = [r for r in answerable if r["recall@5"] < 1.0]
    return {
        # Ideal: abstention_rate = 1.0 (dijo "no sé" en todas).
        "unanswerable": _counts(unanswerable),
        # Ideal: abstention_rate = 0.0 (tenía la evidencia completa y respondió).
        "answerable_full_context": _counts(full),
        # Le faltaba evidencia: aquí abstenerse no es un error del LLM.
        "answerable_partial_context": _counts(partial),
        "by_lang": {
            lang: {
                "unanswerable": _counts([r for r in unanswerable if r["lang"] == lang]),
                "answerable_full_context": _counts([r for r in full if r["lang"] == lang]),
            }
            for lang in ("es", "en")
        },
    }


def _short(text: str, width: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def print_report(summary: dict, records: list[dict]) -> None:
    def line(name: str, c: dict) -> str:
        rate = "-" if c["abstention_rate"] is None else f"{c['abstention_rate']:.2f}"
        return (
            f"{name:<34}{c['n']:>4}{c['abstained']:>11}{c['mixed']:>7}{c['answered']:>10}{rate:>11}"
        )

    print(f"{'':<34}{'n':>4}{'abstained':>11}{'mixed':>7}{'answered':>10}{'tasa':>11}")
    print(line("sin respuesta (ideal tasa 1)", summary["unanswerable"]))
    print(line("respondibles, contexto completo (0)", summary["answerable_full_context"]))
    print(line("respondibles, contexto parcial", summary["answerable_partial_context"]))
    for lang, groups in summary["by_lang"].items():
        print(line(f"  {lang}: sin respuesta", groups["unanswerable"]))
        print(line(f"  {lang}: contexto completo", groups["answerable_full_context"]))

    # Lo que hay que mirar a mano: dónde la etiqueta automática puede estar mal o el LLM se equivocó.
    review = [
        r
        for r in records
        if (r["kind"] == "unanswerable") != (r["verdict"] == "abstained") or r["verdict"] == "mixed"
    ]
    if review:
        print("\nPara revisar a mano:")
        for r in review:
            context = f" recall@5={r['recall@5']:.1f}" if "recall@5" in r else ""
            print(f"  {r['id']} [{r['kind']}, {r['lang']}{context}] {r['verdict']}")
            print(f"    P: {_short(r['question'])}")
            print(f"    R: {_short(r['answer'])}")


def main() -> None:
    from ldr.config import get_settings
    from ldr.db import connect
    from ldr.embed.fastembed_impl import FastembedEmbedder
    from ldr.evals.run import golden_hash, save
    from ldr.generate.gemini_client import GeminiClient
    from ldr.retrieve.retriever import Retriever

    parser = argparse.ArgumentParser(description="Respuestas del sistema y su abstención")
    parser.add_argument("--golden", type=Path, default=Path("evals/golden/golden.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/evals/answers.jsonl"))
    parser.add_argument("--delay", type=float, default=6.0, help="segundos entre llamadas a Gemini")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    settings = get_settings()
    if settings.gemini_api_key is None:
        raise SystemExit("Falta GEMINI_API_KEY en .env")
    # El MISMO modelo que responde en /ask (no el rápido): se mide lo que ve el usuario. Reintentos
    # largos como en golden_gen: un lote puede esperar a que se le pase la saturación a Gemini.
    llm = GeminiClient(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_model,
        timeout_s=60,
        max_attempts=5,
        base_delay=5.0,
    )
    items = load(args.golden)
    cache = AnswerCache(args.cache)
    print(f"{len(items)} preguntas · {STRATEGY}·{MODE} k={K} · {llm.model} · {len(cache)} en caché")

    retriever = Retriever(
        FastembedEmbedder(settings.embedding_model, settings.models_dir), strategy=STRATEGY
    )
    start = time.perf_counter()
    with connect() as conn:
        run = answer_all(
            items,
            lambda q: retriever.search(conn, q, mode=MODE, k=K),
            llm,
            cache,
            delay_s=args.delay,
        )
    print(
        f"{len(run.records)} respuestas · {run.llm_calls} llamadas nuevas a Gemini · "
        f"{time.perf_counter() - start:.0f}s\n"
    )

    summary = summarize(run.records)
    print_report(summary, run.records)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now()
    out = args.out_dir / f"answers-{created:%Y%m%d-%H%M%S}.json"
    save(
        {
            "created": created.isoformat(timespec="seconds"),
            "complete": run.complete,
            "golden": {"path": args.golden.as_posix(), "sha256": golden_hash(args.golden)},
            "config": {"strategy": STRATEGY, "mode": MODE, "k": K},
            "llm_model": llm.model,
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12],
            "summary": summary,
            "questions": run.records,
        },
        out,
    )
    print(f"\nResultados en {out}")
    if not run.complete:
        print("AVISO: Gemini se cayó a la mitad. Vuelve a correrlo: sigue desde la caché.")


if __name__ == "__main__":
    main()
