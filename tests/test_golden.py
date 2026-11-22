import json
import random

from ldr.evals.golden import Evidence, GoldenItem, append, contains, load, normalize, save
from ldr.evals.golden_gen import GoldenGenerator, eligible_sections
from ldr.generate.llm import LLMUnavailableError
from ldr.ingest.loader import Document

PROSE = (
    "Query parameters that are not part of the path are interpreted automatically. "
    "When you declare a default value, the parameter becomes **optional** for the client. "
) * 4  # > 400 caracteres de prosa


def doc(path: str, text: str) -> Document:
    return Document(path, "Query Parameters", f"https://x/{path}", text, "hash")


DOCS = [
    doc(
        "tutorial/query-params.md",
        f"# Query Parameters {{ #query-parameters }}\n\n{PROSE}\n\n## Defaults {{ #defaults }}\n\n{PROSE}",
    ),
    doc("reference/apirouter.md", f"# APIRouter\n\n{PROSE}"),  # referencia: se salta
    doc("tutorial/tiny.md", "# Tiny\n\nPoco texto."),  # sin prosa suficiente
]

GOOD_QUOTE = "When you declare a default value, the parameter becomes optional for the client."


class FakeLLM:
    """Devuelve las respuestas guionadas, validadas con el esquema pedido, como hace GeminiClient."""

    model = "fake"

    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls = 0

    def generate_json(self, system, user, schema, *, temperature=0.2):
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return schema.model_validate_json(json.dumps(response))


def single(quote: str) -> dict:
    return {
        "question": "¿Cómo hago opcional un parámetro?",
        "quote": quote,
        "reference_answer": "...",
    }


def test_normalize_ignores_formatting_but_keeps_underscores() -> None:
    assert normalize("Use **`response_model`**\n  in [the decorator](https://x)") == (
        "use response_model in the decorator"
    )
    assert contains(PROSE, GOOD_QUOTE)  # el LLM quitó los ** de "optional": igual cuenta
    assert not contains(PROSE, "the parameter is always required")


def test_only_pages_with_enough_prose_are_used() -> None:
    by_page = eligible_sections(DOCS)
    assert list(by_page) == ["tutorial/query-params.md"]
    assert len(by_page["tutorial/query-params.md"]) == 2


def test_a_quote_that_is_not_in_the_source_is_rejected_and_retried() -> None:
    llm = FakeLLM(
        [single("Parameters are optional by default in FastAPI always."), single(GOOD_QUOTE)]
    )
    generator = GoldenGenerator(llm, random.Random(0))

    items = generator.generate(DOCS, n_single=1, n_multi=0, n_unanswerable=0)

    assert [i.evidence[0].quote for i in items] == [GOOD_QUOTE]
    assert generator.stats.rejected["quote_not_in_source"] == 1
    assert llm.calls == 2


def test_invalid_json_counts_as_a_failed_attempt() -> None:
    llm = FakeLLM([{"question": "sin quote"}, {"question": "tampoco"}])
    generator = GoldenGenerator(llm, random.Random(0))

    assert generator.generate(DOCS, n_single=1, n_multi=0, n_unanswerable=0) == []
    assert generator.stats.rejected["invalid_json"] == 2


def test_multi_needs_a_valid_quote_from_each_section() -> None:
    multi = {"question": "q", "quote_a": GOOD_QUOTE, "quote_b": GOOD_QUOTE, "reference_answer": "r"}
    unanswerable = {
        "questions": [
            {"question": "¿Cómo despliego FastAPI en Heroku?", "key_terms": ["Heroku"]},
            {"question": "otra que sobra", "key_terms": ["Kafka"]},
        ]
    }
    llm = FakeLLM([multi, unanswerable])
    generator = GoldenGenerator(llm, random.Random(0))

    items = generator.generate(DOCS, n_single=0, n_multi=1, n_unanswerable=1)

    assert [(i.id, i.kind, len(i.evidence)) for i in items] == [
        ("q001", "multi", 2),
        ("q002", "unanswerable", 0),
    ]
    assert items[0].unit_ids() == {"q001#e1", "q001#e2"}


def test_save_and_load_round_trip(tmp_path) -> None:
    item = GoldenItem(
        id="q001",
        question="¿Cómo hago opcional un parámetro?",
        lang="es",
        kind="single",
        evidence=[Evidence(path="tutorial/query-params.md", section="Defaults", quote=GOOD_QUOTE)],
        reference_answer="Dándole un valor por defecto.",
    )
    path = tmp_path / "golden.jsonl"
    save([item], path)
    assert load(path) == [item]


DOWN = LLMUnavailableError("503")


def test_a_single_outage_skips_that_question_and_keeps_going() -> None:
    llm = FakeLLM([DOWN, single(GOOD_QUOTE)])
    generator = GoldenGenerator(llm, random.Random(0))

    items = generator.generate(DOCS, n_single=1, n_multi=0, n_unanswerable=0)

    assert len(items) == 1
    assert generator.stats.rejected["llm_unavailable"] == 1
    assert not generator.stats.gave_up


def test_a_sustained_outage_stops_but_keeps_what_was_generated() -> None:
    # single sale bien; luego multi falla 2 veces y la primera no respondible, 3 seguidas: se para.
    llm = FakeLLM([single(GOOD_QUOTE), DOWN, DOWN, DOWN])
    generator = GoldenGenerator(llm, random.Random(0))

    items = generator.generate(DOCS, n_single=1, n_multi=1, n_unanswerable=2)

    assert [(i.id, i.kind) for i in items] == [("q001", "single")]
    assert generator.stats.gave_up
    assert llm.calls == 4


def test_each_item_is_saved_as_soon_as_it_is_made_and_a_run_can_resume(tmp_path) -> None:
    out = tmp_path / "candidates.jsonl"
    multi = {"question": "q", "quote_a": GOOD_QUOTE, "quote_b": GOOD_QUOTE, "reference_answer": "r"}

    # 1ª corrida: sale la single y Gemini se cae para siempre.
    first = GoldenGenerator(FakeLLM([single(GOOD_QUOTE), DOWN, DOWN, DOWN]), random.Random(0))
    first.generate(DOCS, n_single=1, n_multi=1, n_unanswerable=0, on_item=lambda i: append(i, out))
    assert [i.kind for i in load(out)] == ["single"]  # quedó en disco aunque la corrida falló

    # 2ª corrida: retoma, no repite la single (ninguna llamada para ella) y numera desde q002.
    llm = FakeLLM([multi])
    items = GoldenGenerator(llm, random.Random(0)).generate(
        DOCS,
        n_single=1,
        n_multi=1,
        n_unanswerable=0,
        done=load(out),
        on_item=lambda i: append(i, out),
    )
    assert llm.calls == 1
    assert [(i.id, i.kind) for i in items] == [("q001", "single"), ("q002", "multi")]
    assert [i.id for i in load(out)] == ["q001", "q002"]


def test_unanswerable_questions_whose_terms_appear_in_the_docs_are_dropped() -> None:
    # "parameters" está en el corpus de prueba: esa pregunta sí podría responderse.
    unanswerable = {
        "questions": [
            {"question": "¿Cómo uso query parameters?", "key_terms": ["parameters"]},
            {"question": "¿Sin términos?", "key_terms": []},
            {"question": "¿Cómo conecto FastAPI con Kafka?", "key_terms": ["Kafka"]},
        ]
    }
    generator = GoldenGenerator(FakeLLM([unanswerable]), random.Random(0))

    items = generator.generate(DOCS, n_single=0, n_multi=0, n_unanswerable=1)

    assert [i.question for i in items] == ["¿Cómo conecto FastAPI con Kafka?"]
    assert generator.stats.rejected["unanswerable_in_docs"] == 1
    assert generator.stats.rejected["unanswerable_no_terms"] == 1


def test_a_term_only_counts_as_a_whole_word() -> None:
    # "AWS" no debe calzar dentro de "laws"; si calzara, se botaría una pregunta válida.
    docs = [*DOCS, doc("tutorial/laws.md", "# Laws\n\nThe laws of physics.")]
    unanswerable = {"questions": [{"question": "¿FastAPI en AWS?", "key_terms": ["AWS"]}]}
    generator = GoldenGenerator(FakeLLM([unanswerable]), random.Random(0))

    assert len(generator.generate(docs, n_single=0, n_multi=0, n_unanswerable=1)) == 1


def test_multi_prefers_pages_without_a_single_question() -> None:
    other = doc("tutorial/other.md", f"# Other\n\n{PROSE}\n\n## More\n\n{PROSE}")
    multi = {"question": "q", "quote_a": GOOD_QUOTE, "quote_b": GOOD_QUOTE, "reference_answer": "r"}
    generator = GoldenGenerator(FakeLLM([single(GOOD_QUOTE), multi]), random.Random(0))

    items = generator.generate([*DOCS, other], n_single=1, n_multi=1, n_unanswerable=0)

    single_page, multi_page = (i.evidence[0].path for i in items)
    assert single_page != multi_page


def test_new_ids_continue_after_the_highest_even_if_some_were_deleted() -> None:
    kept = GoldenItem(
        id="q007", question="x", lang="es", kind="multi", evidence=[], reference_answer=None
    )
    generator = GoldenGenerator(FakeLLM([single(GOOD_QUOTE)]), random.Random(0))

    items = generator.generate(DOCS, n_single=1, n_multi=0, n_unanswerable=0, done=[kept])

    assert [i.id for i in items] == ["q007", "q008"]
