from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno o de .env (las variables de entorno ganan)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ldr:ldr@localhost:5433/ldr"
    # SecretStr evita que la key aparezca en logs o en un print(settings).
    gemini_api_key: SecretStr | None = None

    # Recomendados por Google para proyectos nuevos (ai.google.dev/gemini-api/docs/models, oct-2026).
    # gemini-3.8-flash es el recomendado, pero el 2026-10-29 daba 504/timeout en el free tier: 3.6 es la
    # generación anterior estable. Se cambia con GEMINI_MODEL en .env.
    gemini_model: str = "gemini-3.6-flash"  # responde
    # Tareas auxiliares: juez de los evals, reescritura de consultas.
    gemini_fast_model: str = "gemini-3.5-flash-lite"

    # Orígenes que pueden llamar a la API desde un navegador (el frontend Next.js).
    cors_origins: list[str] = ["http://localhost:3000"]

    corpus_dir: Path = Path("data/fastapi")
    embedding_model: str = "google/embeddinggemma-300m"
    # Por defecto fastembed usa %TEMP%, que Windows puede limpiar solo (y habría que bajar 1.2 GB otra vez).
    models_dir: Path = Path(".cache/models")
    # Cross-encoder multilingüe cuantizado a int8 (~0.57 GB): reordena los candidatos de la búsqueda.
    reranker_model: str = "BAAI/bge-reranker-v2-m3-int8"
    warmup_models: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
