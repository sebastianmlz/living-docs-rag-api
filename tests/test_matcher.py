from ldr.evals.golden import Evidence, GoldenItem
from ldr.evals.matcher import covered_units, to_ranking, unreachable_units
from ldr.retrieve.hit import Hit

QUOTE_A = "When you declare a default value, the parameter becomes optional."
QUOTE_B = "You can also declare bool types, and they will be converted."

ITEM = GoldenItem(
    id="q007",
    question="?",
    lang="en",
    kind="multi",
    evidence=[
        Evidence(path="tutorial/query-params.md", section="Defaults", quote=QUOTE_A),
        Evidence(path="tutorial/query-params.md", section="Bool", quote=QUOTE_B),
    ],
    reference_answer="...",
)


def hit(path: str, content: str) -> Hit:
    return Hit(1, path, "T", "https://x/", None, (), content, 0.5)


def test_a_chunk_covers_an_evidence_from_the_same_page_despite_formatting() -> None:
    content = (
        "## Defaults\n\nWhen you declare a **default** value,\nthe parameter becomes `optional`."
    )
    assert covered_units("tutorial/query-params.md", content, ITEM) == {"q007#e1"}


def test_the_same_text_in_another_page_does_not_count() -> None:
    # Puede que otra página repita la frase, pero la evidencia es de query-params.
    assert covered_units("tutorial/body.md", QUOTE_A, ITEM) == frozenset()


def test_one_chunk_can_cover_both_evidences() -> None:
    ranking = to_ranking(
        [
            hit("tutorial/body.md", "nada"),
            hit("tutorial/query-params.md", f"{QUOTE_A}\n\n{QUOTE_B}"),
        ],
        ITEM,
    )
    assert ranking == [frozenset(), {"q007#e1", "q007#e2"}]


def test_an_evidence_cut_in_half_by_the_chunker_is_unreachable() -> None:
    half = len(QUOTE_B) // 2
    chunks = [
        ("tutorial/query-params.md", f"intro. {QUOTE_A}"),
        ("tutorial/query-params.md", f"... {QUOTE_B[:half]}"),  # el chunk termina a mitad de frase
        ("tutorial/query-params.md", f"{QUOTE_B[half:]} ..."),
    ]
    assert unreachable_units(chunks, [ITEM]) == ["q007#e2"]
