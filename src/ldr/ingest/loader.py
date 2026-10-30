"""Lee la documentación de FastAPI: archivos markdown, sus includes de código y lo necesario para citar."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DOCS_BASE_URL = "https://fastapi.tiangolo.com/"
# release-notes: changelog enorme y repetitivo, mete ruido sin responder preguntas de uso.
# _llm-test: archivo interno de FastAPI para probar sus traducciones con LLM, no es documentación.
EXCLUDED = frozenset({"release-notes.md", "_llm-test.md"})

# Dos sintaxis de include en estas docs:
#   {* ../../docs_src/query_params/tutorial001_py310.py hl[9] *}   directiva suelta → bloque de código
#   {!../../docs_src/app.py!}                                        ya va dentro de un bloque ```
_INCLUDE = re.compile(r"\{\*\s*(?P<star>\S+).*?\*\}|\{!\s*(?P<bang>[^!\s]+)\s*!\}")
_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_HEADING_ID = re.compile(r"\s*\{\s*#(?P<anchor>[\w-]+)\s*\}\s*$")
_LANGUAGES = {".py": "python", ".toml": "toml", ".json": "json", ".sh": "bash", ".md": "markdown"}


@dataclass(frozen=True)
class Document:
    path: str  # relativa a docs/en/docs, con "/" (tutorial/query-params.md)
    title: str
    url: str
    text: str  # markdown con los includes ya resueltos
    content_hash: str


def split_heading(raw: str) -> tuple[str, str | None]:
    """'Defaults { #defaults }' → ('Defaults', 'defaults')."""
    match = _HEADING_ID.search(raw)
    if not match:
        return raw.strip(), None
    return raw[: match.start()].strip(), match["anchor"]


def page_url(path: str) -> str:
    """tutorial/query-params.md → https://fastapi.tiangolo.com/tutorial/query-params/"""
    page = path.removesuffix(".md")
    if page == "index":
        return DOCS_BASE_URL
    return f"{DOCS_BASE_URL}{page.removesuffix('/index')}/"


def resolve_includes(markdown: str, lang_root: Path, repo_root: Path) -> str:
    """Reemplaza cada include por el contenido del archivo al que apunta.

    El corpus viene de un repo externo: una ruta como ../../../etc/passwd no debe salir del repo clonado.
    """

    def replace(match: re.Match[str]) -> str:
        ref = match["star"] or match["bang"]
        target = (lang_root / ref).resolve()
        if not target.is_relative_to(repo_root) or not target.is_file():
            return f"<!-- include no disponible: {ref} -->"
        code = target.read_text(encoding="utf-8").rstrip()
        if match["star"]:
            return f"```{_LANGUAGES.get(target.suffix, '')}\n{code}\n```"
        return code

    return _INCLUDE.sub(replace, markdown)


def load_documents(repo_dir: Path) -> list[Document]:
    """Todos los .md de docs/en/docs, ordenados por ruta para que cada corrida sea reproducible."""
    repo_root = repo_dir.resolve()
    lang_root = repo_root / "docs" / "en"
    docs_root = lang_root / "docs"
    if not docs_root.is_dir():
        raise FileNotFoundError(f"No existe {docs_root}: ¿faltó el git sparse-checkout?")

    documents = []
    for file in sorted(docs_root.rglob("*.md")):
        path = file.relative_to(docs_root).as_posix()
        if path in EXCLUDED:
            continue
        text = resolve_includes(file.read_text(encoding="utf-8"), lang_root, repo_root)
        title_match = _TITLE.search(text)
        title = split_heading(title_match[1])[0] if title_match else path
        # El hash es del texto YA resuelto: si cambia un ejemplo de docs_src, el documento se reprocesa.
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        documents.append(Document(path, title, page_url(path), text, content_hash))
    return documents
