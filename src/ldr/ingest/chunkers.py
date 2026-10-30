"""Estrategias de chunking. Todas miden en tokens del modelo de embeddings, no en caracteres."""

from collections.abc import Callable
from dataclasses import dataclass

from ldr.ingest.markdown import parse_sections, split_blocks

TokenCounter = Callable[[str], int]

# De la separación más "natural" a la más brusca.
SEPARATORS = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    content: str
    heading_path: tuple[str, ...]
    anchor: str | None
    token_count: int


def split_recursive(
    text: str, count: TokenCounter, max_tokens: int, overlap: int = 0, separators=SEPARATORS
) -> list[str]:
    """Trozos de hasta `max_tokens`, cortando por el separador más grueso que funcione.

    1. Si el texto cabe, es un solo trozo.
    2. Si no, se parte por el primer separador; las piezas que siguen siendo grandes se parten con el siguiente.
    3. Las piezas se vuelven a juntar hasta llenar `max_tokens`, repitiendo al inicio de cada trozo
       las últimas piezas del anterior (hasta `overlap` tokens) para no perder contexto en el corte.
    """
    pieces = _pieces(text, count, max_tokens, separators)
    chunks: list[str] = []
    current: list[tuple[str, int]] = []
    for piece in pieces:
        n = count(piece)
        if current and sum(t for _, t in current) + n > max_tokens:
            chunks.append("".join(p for p, _ in current))
            tail: list[tuple[str, int]] = []
            for p, t in reversed(current):
                if sum(x for _, x in tail) + t > overlap:
                    break
                tail.insert(0, (p, t))
            current = tail
        current.append((piece, n))
    if current:
        chunks.append("".join(p for p, _ in current))
    return [c.strip() for c in chunks if c.strip()]


def _pieces(
    text: str, count: TokenCounter, max_tokens: int, separators: tuple[str, ...]
) -> list[str]:
    if count(text) <= max_tokens:
        return [text]
    if not separators:
        # Sin separadores (una "palabra" gigante): mitad y mitad hasta que quepa.
        mid = len(text) // 2
        return _pieces(text[:mid], count, max_tokens, ()) + _pieces(
            text[mid:], count, max_tokens, ()
        )
    sep, rest = separators[0], separators[1:]
    parts = text.split(sep)
    if len(parts) == 1:
        return _pieces(text, count, max_tokens, rest)
    out: list[str] = []
    for i, part in enumerate(parts):
        piece = (
            part + sep if i < len(parts) - 1 else part
        )  # se conserva el separador: unir devuelve el texto
        out.extend(_pieces(piece, count, max_tokens, rest))
    return out


def recursive_chunks(
    text: str, count: TokenCounter, max_tokens: int = 400, overlap: int = 60
) -> list[Chunk]:
    """Línea base: ignora la estructura del documento (no sabe de secciones ni de bloques de código)."""
    return [
        Chunk(i, content, (), None, count(content))
        for i, content in enumerate(split_recursive(text, count, max_tokens, overlap))
    ]


def markdown_chunks(
    text: str, count: TokenCounter, max_tokens: int = 400, min_tokens: int = 80
) -> list[Chunk]:
    """Respeta la estructura: corta por secciones, nunca parte un bloque de código que quepa entero,
    y guarda la ruta de encabezados y el ancla para citar la sección exacta.

    Las secciones muy cortas se unen a la vecina: un chunk de 10 tokens casi no tiene significado propio.
    """
    pieces: list[tuple[tuple[str, ...], str | None, str, int]] = []
    for section in parse_sections(text):
        buffer: list[str] = []
        buffer_tokens = 0

        def emit(head=section.heading_path, anchor=section.anchor) -> None:
            nonlocal buffer, buffer_tokens
            if buffer:
                pieces.append((head, anchor, "\n\n".join(buffer), buffer_tokens))
            buffer, buffer_tokens = [], 0

        for block in split_blocks(section.text):
            n = count(block)
            if n > max_tokens:
                # Un bloque que no cabe solo (un ejemplo de código largo): se parte por líneas.
                emit()
                for part in split_recursive(block, count, max_tokens):
                    pieces.append((section.heading_path, section.anchor, part, count(part)))
                continue
            if buffer and buffer_tokens + n > max_tokens:
                emit()
            buffer.append(block)
            buffer_tokens += n
        emit()

    merged: list[tuple[tuple[str, ...], str | None, str, int]] = []
    for head, anchor, content, n in pieces:
        if merged:
            p_head, p_anchor, p_content, p_n = merged[-1]
            if (p_n < min_tokens or n < min_tokens) and p_n + n <= max_tokens:
                merged[-1] = (p_head, p_anchor, f"{p_content}\n\n{content}", p_n + n)
                continue
        merged.append((head, anchor, content, n))

    return [
        Chunk(i, content, head, anchor, count(content))
        for i, (head, anchor, content, _n) in enumerate(merged)
    ]


STRATEGIES: dict[str, Callable[[str, TokenCounter], list[Chunk]]] = {
    "recursive": recursive_chunks,
    "markdown": markdown_chunks,
}
