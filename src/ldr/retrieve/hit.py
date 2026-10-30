from dataclasses import dataclass

# Columnas que toda búsqueda devuelve, en este orden (ver `Hit.from_row`).
HIT_COLUMNS = "c.id, d.path, d.title, d.url, c.anchor, c.heading_path, c.content"


@dataclass(frozen=True)
class Hit:
    """Un chunk recuperado, con lo necesario para mostrarlo y citarlo."""

    chunk_id: int
    path: str
    title: str
    url: str
    anchor: str | None
    heading_path: tuple[str, ...]
    content: str
    # Depende de quién lo produjo: similitud coseno, ts_rank, puntaje RRF o del reranker.
    # No son comparables entre sí.
    score: float

    @classmethod
    def from_row(cls, row: tuple) -> "Hit":
        chunk_id, path, title, url, anchor, heading_path, content, score = row
        return cls(chunk_id, path, title, url, anchor, tuple(heading_path), content, float(score))

    @property
    def citation_url(self) -> str:
        return f"{self.url}#{self.anchor}" if self.anchor else self.url

    @property
    def section(self) -> str:
        return " > ".join(self.heading_path) or self.title
