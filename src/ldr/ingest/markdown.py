"""Estructura del markdown: secciones por encabezado y bloques que no se deben partir."""

import re
from dataclasses import dataclass

from ldr.ingest.loader import split_heading

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class Section:
    heading_path: tuple[str, ...]  # ('Query Parameters', 'Defaults')
    anchor: str | None
    text: str  # markdown de la sección, empezando por su propio encabezado


def parse_sections(markdown: str) -> list[Section]:
    """Corta el documento en cada encabezado.

    Las líneas dentro de un bloque de código no son encabezados: un `# comentario` de Python no abre sección.
    """
    sections: list[Section] = []
    path: list[str] = []
    anchor: str | None = None
    lines: list[str] = []
    fence: str | None = None

    def flush() -> None:
        text = "\n".join(lines).strip()
        if text:
            sections.append(Section(tuple(path), anchor, text))

    for line in markdown.splitlines():
        if fence:
            if line.strip().startswith(fence):
                fence = None
        elif match := _FENCE.match(line):
            fence = match[1]
        elif match := _HEADING.match(line):
            flush()
            lines = []
            level = len(match[1])
            title, anchor = split_heading(match[2])
            path = [*path[: level - 1], title]
            line = f"{match[1]} {title}"  # sin el { #ancla }, que es ruido para el embedding
        lines.append(line)
    flush()
    return sections


def split_blocks(text: str) -> list[str]:
    """Párrafos separados por línea en blanco; un bloque de código o un aviso (/// tip ... ///) es un solo bloque."""
    blocks: list[str] = []
    current: list[str] = []
    fence: str | None = None
    in_admonition = False

    for line in text.splitlines():
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
        elif match := _FENCE.match(line):
            fence = match[1]
        elif stripped.startswith("///"):
            in_admonition = stripped != "///" or not in_admonition
        elif not stripped and not in_admonition:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks
