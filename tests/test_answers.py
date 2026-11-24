"""El runner de respuestas sin BD ni Gemini: la búsqueda y el LLM son falsos."""

from ldr.evals.answers import AnswerCache, answer_all, classify, generate, summarize
from ldr.evals.golden import Evidence, GoldenItem
from ldr.generate.llm import Delta, LLMUnavailableError, Usage
from ldr.generate.prompts import NO_ANSWER
from ldr.retrieve.hit import Hit

QUOTE = "When you declare a default value, the parameter becomes optional."


class ScriptedLLM:
    """Responde lo que diga `script` según la pregunta; `fail_on` simula que Gemini se cae."""

    model = "fake-llm"

    def __init__(self, script: dict[str, str], fail_on: str | None = None) -> None:
        self.script = script
        self.fail_on = fail_on
        self.calls = 0

    def stream(self, system: str, user: str):
        self.calls += 1
        question = user.rsplit("Pregunta: ", 1)[1]
        if question == self.fail_on:
            raise LLMUnavailableError("down")
        text = self.script[question]
        yield Delta(text=text[:5])
        yield Delta(text=text[5:])
        yield Delta(usage=Usage(100, 10))


def hit(content: str, path: str = "tutorial/query-params.md", chunk_id: int = 1) -> Hit:
    return Hit(chunk_id, path, "Query Parameters", "https://x", None, ("Defaults",), content, 0.6)


def item(id_: str, question: str, kind: str = "single", lang: str = "en") -> GoldenItem:
    evidence = (
        []
        if kind == "unanswerable"
        else [Evidence(path="tutorial/query-params.md", section="Defaults", quote=QUOTE)]
    )
    return GoldenItem(
        id=id_,
        question=question,
        lang=lang,
        kind=kind,
        evidence=evidence,
        reference_answer=None if kind == "unanswerable" else "Con un default.",
    )


def search_with(content: str):
    return lambda question: [hit(content)]


# --- classify ---------------------------------------------------------------------------------


def test_classify_exact_and_tolerant_of_quotes_and_bold():
    assert classify(NO_ANSWER) == "abstained"
    assert classify(f'  "{NO_ANSWER}"\n') == "abstained"
    assert classify(f"**{NO_ANSWER}**") == "abstained"


def test_classify_mixed_when_it_answers_and_also_abstains():
    assert classify(f"Usa `None` como default [1]. {NO_ANSWER}") == "mixed"


def test_classify_answered():
    assert classify("Usa `None` como valor por defecto [1].") == "answered"
    # Traducida al inglés no se reconoce: por eso el reporte la deja para revisar a mano.
    assert classify("I couldn't find this in the FastAPI docs.") == "answered"


# --- generate ---------------------------------------------------------------------------------


def test_generate_joins_the_stream_and_keeps_usage():
    llm = ScriptedLLM({"q?": "Usa None [1]."})
    out = generate(llm, "q?", [hit(QUOTE)])
    assert out.text == "Usa None [1]."
    assert (out.llm_called, out.input_tokens, out.output_tokens) == (True, 100, 10)


def test_generate_without_hits_does_not_call_the_llm():
    llm = ScriptedLLM({})
    out = generate(llm, "q?", [])
    assert out.text == NO_ANSWER
    assert not out.llm_called
    assert llm.calls == 0


# --- answer_all + cache -----------------------------------------------------------------------


def test_second_run_is_served_from_the_cache_file(tmp_path):
    items = [item("q001", "a?"), item("q051", "b?", kind="unanswerable")]
    llm = ScriptedLLM({"a?": "Usa None [1].", "b?": NO_ANSWER})
    path = tmp_path / "answers.jsonl"

    first = answer_all(items, search_with(QUOTE), llm, AnswerCache(path))
    assert first.complete and first.llm_calls == 2

    # Otra instancia de la caché: lee lo que quedó en disco, como en una corrida nueva.
    second = answer_all(items, search_with(QUOTE), llm, AnswerCache(path))
    assert second.llm_calls == 0
    assert llm.calls == 2
    assert [r["cached"] for r in second.records] == [True, True]
    assert [r["answer"] for r in second.records] == ["Usa None [1].", NO_ANSWER]


def test_different_context_misses_the_cache(tmp_path):
    items = [item("q001", "a?")]
    llm = ScriptedLLM({"a?": "Usa None [1]."})
    cache = AnswerCache(tmp_path / "answers.jsonl")
    answer_all(items, search_with(QUOTE), llm, cache)
    answer_all(items, search_with("otro chunk"), llm, cache)  # la búsqueda trajo otra cosa
    assert llm.calls == 2


def test_outage_stops_and_keeps_what_was_done(tmp_path):
    items = [item("q001", "a?"), item("q002", "b?"), item("q003", "c?")]
    llm = ScriptedLLM({"a?": "A [1].", "b?": "B [1].", "c?": "C [1]."}, fail_on="b?")
    path = tmp_path / "answers.jsonl"

    run = answer_all(items, search_with(QUOTE), llm, AnswerCache(path))
    assert not run.complete
    assert [r["id"] for r in run.records] == ["q001"]

    llm.fail_on = None  # Gemini volvió: la segunda corrida solo paga lo que faltaba
    run = answer_all(items, search_with(QUOTE), llm, AnswerCache(path))
    assert run.complete and run.llm_calls == 2


def test_record_measures_the_context_the_llm_saw(tmp_path):
    items = [item("q001", "a?"), item("q002", "b?")]
    llm = ScriptedLLM({"a?": "A [1].", "b?": NO_ANSWER})
    run = answer_all(items, search_with(QUOTE), llm, AnswerCache(tmp_path / "a.jsonl"))
    assert run.records[0]["recall@5"] == 1.0

    run = answer_all(items, search_with("nada que ver"), llm, AnswerCache(tmp_path / "b.jsonl"))
    assert run.records[1]["recall@5"] == 0.0


# --- summarize --------------------------------------------------------------------------------


def row(kind: str, verdict: str, lang: str = "en", recall: float | None = 1.0) -> dict:
    r = {"kind": kind, "verdict": verdict, "lang": lang}
    if kind != "unanswerable":
        r["recall@5"] = recall
    return r


def test_summarize_separates_llm_mistakes_from_retrieval_misses():
    records = [
        row("unanswerable", "abstained"),
        row("unanswerable", "answered", lang="es"),  # inventó: error del LLM
        row("single", "answered"),
        row("single", "abstained"),  # tenía la evidencia y se abstuvo: error del LLM
        row("single", "abstained", recall=0.0),  # no tenía la evidencia: abstenerse está bien
        row("multi", "mixed", recall=0.5),
    ]
    s = summarize(records)
    assert s["unanswerable"] == {
        "n": 2,
        "abstained": 1,
        "mixed": 0,
        "answered": 1,
        "abstention_rate": 0.5,
    }
    assert s["answerable_full_context"]["n"] == 2
    assert s["answerable_full_context"]["abstention_rate"] == 0.5
    assert s["answerable_partial_context"] == {
        "n": 2,
        "abstained": 1,
        "mixed": 1,
        "answered": 0,
        "abstention_rate": 0.5,
    }
    assert s["by_lang"]["es"]["unanswerable"]["answered"] == 1
    assert s["by_lang"]["es"]["answerable_full_context"]["abstention_rate"] is None  # sin filas


def test_cache_survives_a_line_cut_in_half(tmp_path):
    """Ctrl+C a mitad de una escritura: la línea rota se descarta y la siguiente no se pega a ella."""
    items = [item("q001", "a?"), item("q002", "b?")]
    llm = ScriptedLLM({"a?": "A [1].", "b?": "B [1]."})
    path = tmp_path / "answers.jsonl"
    answer_all(items[:1], search_with(QUOTE), llm, AnswerCache(path))
    with path.open("a", encoding="utf-8") as f:
        f.write('{"key": "abc", "text": "cort')  # sin cerrar ni salto de línea

    run = answer_all(items, search_with(QUOTE), llm, AnswerCache(path))
    assert [r["cached"] for r in run.records] == [True, False]
    assert len(AnswerCache(path)) == 2  # las dos buenas se leen; la rota no
