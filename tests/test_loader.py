from pathlib import Path

from ldr.ingest.loader import load_documents, page_url, split_heading


def make_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def test_split_heading_extracts_anchor() -> None:
    assert split_heading("Defaults { #defaults }") == ("Defaults", "defaults")
    assert split_heading("No anchor") == ("No anchor", None)


def test_page_url() -> None:
    assert page_url("index.md") == "https://fastapi.tiangolo.com/"
    assert page_url("tutorial/index.md") == "https://fastapi.tiangolo.com/tutorial/"
    assert (
        page_url("tutorial/query-params.md")
        == "https://fastapi.tiangolo.com/tutorial/query-params/"
    )


def test_include_is_inlined_as_code_block(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        {
            "docs/en/docs/tutorial/query.md": "# Query { #query }\n\n{* ../../docs_src/q/app.py hl[1] *}\n",
            "docs_src/q/app.py": "app = FastAPI()\n",
        },
    )
    [doc] = load_documents(repo)

    assert doc.title == "Query"
    assert "```python\napp = FastAPI()\n```" in doc.text


def test_include_outside_repo_is_not_read(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    repo = make_repo(
        tmp_path / "repo", {"docs/en/docs/x.md": "# X\n\n{* ../../../../secret.txt *}\n"}
    )
    [doc] = load_documents(repo)

    assert "TOP SECRET" not in doc.text
    assert "include no disponible" in doc.text


def test_hash_changes_when_included_code_changes(tmp_path: Path) -> None:
    files = {"docs/en/docs/x.md": "# X\n\n{* ../../docs_src/a.py *}\n", "docs_src/a.py": "v = 1\n"}
    before = load_documents(make_repo(tmp_path, files))[0].content_hash
    (tmp_path / "docs_src/a.py").write_text("v = 2\n", encoding="utf-8")
    after = load_documents(tmp_path)[0].content_hash

    assert before != after
