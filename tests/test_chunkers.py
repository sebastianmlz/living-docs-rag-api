from ldr.ingest.chunkers import markdown_chunks, recursive_chunks
from ldr.ingest.markdown import parse_sections, split_blocks


def words(text: str) -> int:
    """Contador de "tokens" falso para los tests: palabras. No depende del modelo."""
    return len(text.split())


DOC = """# Query Parameters { #query-parameters }

Intro paragraph about query parameters.

## Defaults { #defaults }

They can have default values.

```python
# this is a comment, not a heading
def read(skip: int = 0): ...
```

/// tip

A tip with a blank line inside.

///
"""


def test_comment_inside_code_is_not_a_heading() -> None:
    sections = parse_sections(DOC)

    assert [s.heading_path for s in sections] == [
        ("Query Parameters",),
        ("Query Parameters", "Defaults"),
    ]
    assert sections[1].anchor == "defaults"
    assert "{ #defaults }" not in sections[1].text


def test_code_fence_and_admonition_are_single_blocks() -> None:
    blocks = split_blocks(parse_sections(DOC)[1].text)

    assert any(b.startswith("```python") and b.endswith("```") for b in blocks)
    assert any(b.startswith("/// tip") and b.endswith("///") for b in blocks)


def test_recursive_respects_max_and_overlaps() -> None:
    text = "\n\n".join(f"paragraph {i} " + "word " * 30 for i in range(10))
    chunks = recursive_chunks(text, words, max_tokens=100, overlap=40)

    assert len(chunks) > 1
    assert all(c.token_count <= 100 for c in chunks)
    # El final de un chunk se repite al inicio del siguiente.
    assert chunks[0].content.split("\n\n")[-1] in chunks[1].content


def test_markdown_keeps_headings_and_merges_small_sections() -> None:
    chunks = markdown_chunks(DOC, words, max_tokens=200, min_tokens=50)

    # Todo el documento es corto: las dos secciones se unen en un chunk que conserva la primera ruta.
    assert len(chunks) == 1
    assert chunks[0].heading_path == ("Query Parameters",)
    assert "## Defaults" in chunks[0].content


def test_markdown_never_splits_a_code_block_that_fits() -> None:
    code = "```python\n" + "x = 1\n" * 20 + "```"  # 61 palabras: cabe en 100
    doc = "# T\n\n" + "intro " * 60 + "\n\n" + code  # intro + código no caben juntos
    chunks = markdown_chunks(doc, words, max_tokens=100, min_tokens=10)

    assert any(code in c.content for c in chunks)
