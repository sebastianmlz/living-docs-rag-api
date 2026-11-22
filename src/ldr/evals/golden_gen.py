"""Genera los CANDIDATOS del golden set con un LLM. Una persona los revisa antes de usarlos.

python -m ldr.evals.golden_gen   (o: poe golden)

Tres tipos de pregunta:
- single: se responde con UNA sección. Es el caso típico.
- multi: necesita DOS secciones de la misma página. Pone a prueba el recall (¿llegan las dos al top k?).
- unanswerable: suena a FastAPI pero la documentación no la cubre. Sirve para calibrar el umbral: el
  sistema debería responder "no encontré" en vez de inventar.

Mitad en español y mitad en inglés: el corpus está en inglés, así que las preguntas en español miden
si la búsqueda funciona entre idiomas (el modelo de embeddings es multilingüe; tsvector no lo es).

No se confía en el LLM: cada fragmento que dice haber copiado se busca en el documento, y si no está
textual se descarta. Un fragmento inventado haría que la pregunta no se pueda acertar nunca y bajaría
las métricas sin que el sistema tenga la culpa.
"""

import argparse
import logging
import random
import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from ldr.evals.golden import Evidence, GoldenItem, Lang, append, contains, load, normalize
from ldr.generate.llm import LLMUnavailableError
from ldr.ingest.loader import Document, load_documents, page_url
from ldr.ingest.markdown import Section, parse_sections, split_blocks

logger = logging.getLogger(__name__)

# Páginas que no responden preguntas de uso: la referencia de la API es casi toda autogenerada
# (::: fastapi.APIRouter) y las otras hablan del proyecto, no de cómo usar FastAPI.
SKIPPED_PREFIXES = ("reference/",)
SKIPPED_PAGES = frozenset(
    {
        "contributing.md",
        "external-links.md",
        "fastapi-people.md",
        "help-fastapi.md",
        "management.md",
        "management-tasks.md",
        "newsletter.md",
        "translation-banner.md",
        "translations.md",
    }
)
# La portada junta temas sueltos (ejemplo, rendimiento, instalación): una multi de ahí combina cosas sin
# relación y sale artificial (pasó dos veces). Para single sí sirve.
MULTI_SKIPPED_PAGES = frozenset({"index.md"})
MIN_PROSE_CHARS = 400  # menos texto que esto no alcanza para una pregunta con sustancia
MAX_SECTION_CHARS = 6000  # recorte para no gastar tokens en secciones gigantes
QUOTE_WORDS = (5, 50)
MAX_CONSECUTIVE_OUTAGES = 3
UNANSWERABLE_EXTRA = 4  # se piden de más porque el filtro de términos bota algunas
# Alta a propósito: aquí queremos VARIEDAD de preguntas. La fidelidad no la da la temperatura, la da
# el chequeo de los fragmentos en el código.
TEMPERATURE = 0.9

SYSTEM = """\
Ayudas a construir un set de evaluación para un buscador (RAG) sobre la documentación de FastAPI.
Escribes preguntas como las haría un desarrollador real que usa FastAPI.

Reglas:
1. La pregunta se responde SOLO con el texto que se te entrega, sin conocimiento externo.
2. Escribe la pregunta con tus propias palabras. NO copies frases ni encabezados del texto: un usuario
   real no conoce el vocabulario exacto de la documentación.
3. La pregunta no menciona "la sección", "el texto" ni "la documentación": es una duda directa.
4. Cada fragmento (quote) es una copia TEXTUAL y continua del texto entregado: entre 5 y 50 palabras,
   sin cambiar ni una palabra, sin resumir y sin unir trozos separados. De preferencia una oración de
   prosa (no un encabezado). Es la parte que contiene la clave de la respuesta.
5. reference_answer: la respuesta correcta en 1 a 3 oraciones, en el mismo idioma de la pregunta.
"""

LANG_NAMES = {"es": "español", "en": "inglés"}


class SingleDraft(BaseModel):
    question: str
    quote: str
    reference_answer: str


class MultiDraft(BaseModel):
    question: str
    quote_a: str  # sale del texto A
    quote_b: str  # sale del texto B
    reference_answer: str


class UnanswerableQuestion(BaseModel):
    question: str
    # Los nombres propios de la pregunta (Kafka, Firebase...). Si alguno aparece en la documentación,
    # la pregunta probablemente SÍ se responde, al menos en parte, y se descarta.
    key_terms: list[str]


class UnanswerableDraft(BaseModel):
    questions: list[UnanswerableQuestion]


class JsonLLM(Protocol):
    model: str

    def generate_json[T: BaseModel](
        self, system: str, user: str, schema: type[T], *, temperature: float = ...
    ) -> T: ...


@dataclass(frozen=True)
class Candidate:
    document: Document
    section: Section

    @property
    def label(self) -> str:
        return " > ".join(self.section.heading_path) or self.document.title

    def prompt_text(self) -> str:
        return f"Página: {self.document.title}\nSección: {self.label}\n\n{self.section.text[:MAX_SECTION_CHARS]}"


@dataclass
class Stats:
    """Cuántas veces el LLM falló y por qué: es un dato en sí mismo (¿qué tanto inventa?)."""

    calls: int = 0
    rejected: Counter = field(default_factory=Counter)
    gave_up: bool = False  # Gemini se cayó y el set quedó incompleto


class _GeminiDownError(Exception):
    pass


def _prose_chars(section: Section) -> int:
    blocks = split_blocks(section.text)
    prose = [b for b in blocks if not b.lstrip().startswith(("```", "~~~", "#", "{*"))]
    return sum(len(b) for b in prose)


def eligible_sections(documents: list[Document]) -> dict[str, list[Candidate]]:
    """Por página, las secciones con suficiente prosa para sacar una pregunta."""
    by_page: dict[str, list[Candidate]] = {}
    for doc in documents:
        if doc.path in SKIPPED_PAGES or doc.path.startswith(SKIPPED_PREFIXES):
            continue
        candidates = [
            Candidate(doc, s)
            for s in parse_sections(doc.text)
            if _prose_chars(s) >= MIN_PROSE_CHARS
        ]
        if candidates:
            by_page[doc.path] = candidates
    return by_page


def _mentions(corpus: str, term: str) -> bool:
    """¿Aparece el término como palabra completa? ("AWS" no debe calzar dentro de "laws")."""
    return re.search(rf"\b{re.escape(normalize(term))}\b", corpus) is not None


def _quote_problem(quote: str, source: str) -> str | None:
    """Por qué un fragmento no sirve, o None si sirve."""
    words = len(normalize(quote).split())
    if not QUOTE_WORDS[0] <= words <= QUOTE_WORDS[1]:
        return "quote_length"
    if not contains(source, quote):
        return "quote_not_in_source"  # el LLM lo parafraseó o lo inventó
    return None


class GoldenGenerator:
    def __init__(
        self, llm: JsonLLM, rng: random.Random, *, delay_s: float = 0, attempts: int = 2
    ) -> None:
        self.llm = llm
        self.rng = rng
        self.delay_s = delay_s
        self.attempts = attempts
        self.stats = Stats()
        self._outages = 0  # caídas seguidas de Gemini

    def _ask[T: BaseModel](self, user: str, schema: type[T]) -> T | None:
        if self.stats.calls and self.delay_s:
            time.sleep(self.delay_s)  # el free tier limita requests por minuto
        self.stats.calls += 1
        try:
            draft = self.llm.generate_json(SYSTEM, user, schema, temperature=TEMPERATURE)
        except ValidationError:
            self.stats.rejected["invalid_json"] += 1
            return None
        except LLMUnavailableError as exc:
            # Una caída suelta (503 aunque ya se reintentó) no tira todo lo generado: se salta esa
            # pregunta. Varias seguidas ya no son mala suerte, Gemini está caído: se para ahí.
            self.stats.rejected["llm_unavailable"] += 1
            self._outages += 1
            if self._outages >= MAX_CONSECUTIVE_OUTAGES:
                raise _GeminiDownError from exc
            return None
        self._outages = 0
        return draft

    def single(self, candidate: Candidate, lang: Lang) -> GoldenItem | None:
        user = (
            f"Escribe UNA pregunta en {LANG_NAMES[lang]} que se responda con este texto.\n\n"
            f"<texto>\n{candidate.prompt_text()}\n</texto>"
        )
        for _ in range(self.attempts):
            draft = self._ask(user, SingleDraft)
            if draft is None:
                continue
            if problem := _quote_problem(draft.quote, candidate.section.text):
                self.stats.rejected[problem] += 1
                continue
            evidence = Evidence(
                path=candidate.document.path, section=candidate.label, quote=draft.quote
            )
            return GoldenItem(
                id="",
                question=draft.question,
                lang=lang,
                kind="single",
                evidence=[evidence],
                reference_answer=draft.reference_answer,
            )
        return None

    def multi(self, a: Candidate, b: Candidate, lang: Lang) -> GoldenItem | None:
        user = (
            f"Escribe UNA pregunta en {LANG_NAMES[lang]} que necesite información de los DOS textos "
            "para responderse completa (con uno solo quedaría a medias). quote_a sale del texto A y "
            f"quote_b del texto B.\n\n<texto_a>\n{a.prompt_text()}\n</texto_a>\n\n"
            f"<texto_b>\n{b.prompt_text()}\n</texto_b>"
        )
        for _ in range(self.attempts):
            draft = self._ask(user, MultiDraft)
            if draft is None:
                continue
            problem = _quote_problem(draft.quote_a, a.section.text) or _quote_problem(
                draft.quote_b, b.section.text
            )
            if problem:
                self.stats.rejected[problem] += 1
                continue
            return GoldenItem(
                id="",
                question=draft.question,
                lang=lang,
                kind="multi",
                evidence=[
                    Evidence(path=a.document.path, section=a.label, quote=draft.quote_a),
                    Evidence(path=b.document.path, section=b.label, quote=draft.quote_b),
                ],
                reference_answer=draft.reference_answer,
            )
        return None

    def unanswerable(
        self, titles: list[str], n: int, lang: Lang, corpus: str, avoid: Sequence[str] = ()
    ) -> list[GoldenItem]:
        """El LLM no ve el corpus entero, solo los títulos: lo que proponga puede SÍ estar cubierto.

        Por eso se piden más de las necesarias y se descarta toda pregunta con un término clave que
        aparezca en la documentación (`corpus`, ya normalizado). Es un filtro conservador: puede botar
        alguna buena, pero casi no deja pasar una que sí se responda. La revisión humana va igual.
        """
        if n <= 0:
            return []
        avoid_text = "\n".join(f"- {q}" for q in avoid) or "(ninguna)"
        user = (
            f"Estas son las páginas de la documentación de FastAPI:\n{chr(10).join(titles)}\n\n"
            f"Escribe {n + UNANSWERABLE_EXTRA} preguntas en {LANG_NAMES[lang]} que un usuario de "
            "FastAPI haría, que suenen plausibles, pero que esta documentación NO responde: "
            "integraciones con servicios o productos concretos que ninguna de estas páginas "
            "cubriría. Que no sean absurdas ni de otro tema: deben parecer preguntas de FastAPI. "
            "Cada una con key_terms: los nombres propios de servicios o herramientas que menciona "
            f"(no FastAPI ni Python).\n\nNo repitas temas de estas, que ya existen:\n{avoid_text}"
        )
        draft = self._ask(user, UnanswerableDraft)
        if draft is None:
            return []
        kept: list[GoldenItem] = []
        for q in draft.questions:
            if len(kept) == n:
                break
            if not q.key_terms:
                self.stats.rejected["unanswerable_no_terms"] += 1
                continue
            if found := [t for t in q.key_terms if _mentions(corpus, t)]:
                self.stats.rejected["unanswerable_in_docs"] += 1
                logger.info("descartada (la doc menciona %s): %s", found, q.question)
                continue
            kept.append(
                GoldenItem(
                    id="",
                    question=q.question,
                    lang=lang,
                    kind="unanswerable",
                    evidence=[],
                    reference_answer=None,
                )
            )
        return kept

    def generate(
        self,
        documents: list[Document],
        *,
        n_single: int,
        n_multi: int,
        n_unanswerable: int,
        done: Sequence[GoldenItem] = (),
        on_item: Callable[[GoldenItem], None] = lambda _item: None,
    ) -> list[GoldenItem]:
        """Genera lo que falta para llegar a los totales pedidos.

        `done` son las preguntas de una corrida anterior (para retomar). `on_item` se llama apenas
        sale cada pregunta: así se guarda en disco al instante y un corte no borra lo hecho.
        Si Gemini se cae a la mitad, devuelve lo que alcanzó a generar (y marca `stats.gave_up`).
        """
        items = list(done)

        def add(item: GoldenItem) -> None:
            # Siguiente al MAYOR id, no al largo de la lista: si se borraron preguntas a mano, contar
            # repetiría ids que ya existen.
            last = max((int(i.id.removeprefix("q")) for i in items), default=0)
            item = item.model_copy(update={"id": f"q{last + 1:03d}"})
            items.append(item)
            on_item(item)
            logger.info(
                "%s %s · %s", item.id, item.kind, item.evidence[0].path if item.evidence else "-"
            )

        try:
            self._generate(add, items, documents, n_single, n_multi, n_unanswerable)
        except _GeminiDownError:
            self.stats.gave_up = True
            logger.warning("Gemini no responde: queda guardado lo generado hasta ahora")
        return items

    def _generate(
        self,
        add: Callable[[GoldenItem], None],
        items: list[GoldenItem],
        documents: list[Document],
        n_single: int,
        n_multi: int,
        n_unanswerable: int,
    ) -> None:
        by_page = eligible_sections(documents)
        pages = sorted(by_page)
        self.rng.shuffle(pages)
        langs: tuple[Lang, Lang] = ("es", "en")

        def made(kind: str, lang: Lang | None = None) -> list[GoldenItem]:
            return [i for i in items if i.kind == kind and (lang is None or i.lang == lang)]

        def used_pages(kind: str) -> set[str]:
            return {i.evidence[0].path for i in made(kind)}

        # single: como mucho una pregunta por página, así el set cubre más documentación.
        for page in pages:
            if len(made("single")) >= n_single:
                break
            if page in used_pages("single"):
                continue  # ya salió en una corrida anterior
            lang = langs[len(made("single")) % 2]
            if item := self.single(self.rng.choice(by_page[page]), lang):
                add(item)

        # multi: dos secciones distintas de una misma página. Primero las páginas que NO tienen
        # single, para que el set cubra más documentación (sorted es estable: respeta el barajado).
        single_pages = used_pages("single")
        multi_pages = sorted(
            (p for p in pages if len(by_page[p]) >= 2 and p not in MULTI_SKIPPED_PAGES),
            key=lambda p: p in single_pages,
        )
        for page in multi_pages:
            if len(made("multi")) >= n_multi:
                break
            if page in used_pages("multi"):
                continue
            a, b = self.rng.sample(by_page[page], 2)
            if item := self.multi(a, b, langs[len(made("multi")) % 2]):
                add(item)

        titles = sorted({c.document.title for cands in by_page.values() for c in cands})
        corpus = normalize("\n".join(d.text for d in documents))
        half = n_unanswerable // 2
        for lang, wanted in (("es", n_unanswerable - half), ("en", half)):
            missing = wanted - len(made("unanswerable", lang))
            avoid = [i.question for i in made("unanswerable")]
            for item in self.unanswerable(titles, missing, lang, corpus, avoid):
                add(item)


def to_markdown(items: list[GoldenItem], stats: Stats, model: str) -> str:
    """Versión para leer y revisar a mano: el JSONL es para el código, esto es para una persona."""
    kinds = Counter(i.kind for i in items)
    langs = Counter(i.lang for i in items)
    rejected = ", ".join(f"{k}: {v}" for k, v in stats.rejected.most_common()) or "ninguno"
    lines = [
        "# Golden set: candidatos para revisar",
        "",
        f"- Modelo: `{model}` · llamadas: {stats.calls} · descartes: {rejected}",
        f"- {len(items)} preguntas: "
        + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
        + " · "
        + ", ".join(f"{k} {v}" for k, v in sorted(langs.items())),
        "",
        "Al revisar: ¿la pregunta suena real?, ¿el fragmento de verdad la responde?, "
        "¿las no respondibles de verdad NO están en la documentación?",
        "",
    ]
    for item in items:
        lines += [
            "---",
            "",
            f"### {item.id} · {item.kind} · {item.lang}",
            "",
            f"**{item.question}**",
            "",
        ]
        for ev in item.evidence:
            lines += [f"[{ev.path} › {ev.section}]({page_url(ev.path)})", "", f"> {ev.quote}", ""]
        if item.reference_answer:
            lines += [f"*Respuesta esperada:* {item.reference_answer}", ""]
    return "\n".join(lines)


def main() -> None:
    from ldr.config import get_settings
    from ldr.generate.gemini_client import GeminiClient

    parser = argparse.ArgumentParser(description="Genera candidatos para el golden set")
    parser.add_argument("--single", type=int, default=40)
    parser.add_argument("--multi", type=int, default=10)
    parser.add_argument("--unanswerable", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42, help="misma semilla = mismas secciones")
    parser.add_argument("--delay", type=float, default=4.0, help="segundos entre llamadas")
    parser.add_argument("--out", type=Path, default=Path("evals/golden/candidates.jsonl"))
    parser.add_argument(
        "--resume", action="store_true", help="sigue desde lo que ya está en --out, sin repetirlo"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "google_genai"):  # cada request y "AFC is enabled": ruido
        logging.getLogger(noisy).setLevel(logging.WARNING)

    done: list[GoldenItem] = []
    if args.out.exists():
        if not args.resume:
            raise SystemExit(
                f"{args.out} ya existe: usa --resume para seguir o bórralo para empezar de cero"
            )
        done = load(args.out)
        print(f"Retomando: {len(done)} preguntas ya generadas en {args.out}")

    settings = get_settings()
    if settings.gemini_api_key is None:
        raise SystemExit("Falta GEMINI_API_KEY en .env")
    # Un proceso por lotes puede esperar más que un usuario: 5 intentos con esperas de 5, 10, 20 y 40 s
    # aguantan una saturación de Gemini (503) que con los reintentos cortos de la API no alcanza.
    llm = GeminiClient(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_fast_model,
        timeout_s=60,
        max_attempts=5,
        base_delay=5.0,
    )
    # random con semilla para que el muestreo sea reproducible; no es para criptografía.
    rng = random.Random(args.seed)  # noqa: S311
    generator = GoldenGenerator(llm, rng, delay_s=args.delay)
    start = time.perf_counter()
    items = generator.generate(
        load_documents(settings.corpus_dir),
        n_single=args.single,
        n_multi=args.multi,
        n_unanswerable=args.unanswerable,
        done=done,
        on_item=lambda item: append(item, args.out),
    )

    report = args.out.with_suffix(".md")
    report.write_text(to_markdown(items, generator.stats, llm.model), encoding="utf-8")
    print(
        f"{len(items)} preguntas en {args.out} (para leer: {report}) · "
        f"{generator.stats.calls} llamadas · descartes {dict(generator.stats.rejected)} · "
        f"{time.perf_counter() - start:.0f}s"
    )
    if generator.stats.gave_up:
        print("AVISO: Gemini se cayó a la mitad; el set está incompleto. Sigue con --resume.")


if __name__ == "__main__":
    main()
