"""Respuesta en streaming: primero las fuentes, luego el texto pedazo a pedazo, al final las métricas."""

import json
import logging
import time
from collections.abc import Iterator

from ldr.generate.llm import LLMClient, LLMUnavailableError
from ldr.generate.prompts import NO_ANSWER, SYSTEM_PROMPT, build_user_message
from ldr.retrieve.hit import Hit

logger = logging.getLogger(__name__)


def _event(name: str, data: object) -> dict[str, str]:
    """Formato de sse-starlette: cada dict se envía como `event: <name>\\ndata: <json>`."""
    return {"event": name, "data": json.dumps(data, ensure_ascii=False)}


def answer_events(
    llm: LLMClient, question: str, hits: list[Hit], retrieval_ms: float
) -> Iterator[dict[str, str]]:
    yield _event(
        "sources",
        [
            {"id": i, "section": h.section, "url": h.citation_url, "path": h.path}
            for i, h in enumerate(hits, start=1)
        ],
    )

    if not hits:
        # Sin contexto no se llama al LLM: no gasta cuota y no le da la oportunidad de inventar.
        yield _event("delta", {"text": NO_ANSWER})
        yield _event("done", {"retrieval_ms": round(retrieval_ms), "llm_called": False})
        return

    start = time.perf_counter()
    first_token_ms = None
    usage = None
    try:
        for delta in llm.stream(SYSTEM_PROMPT, build_user_message(question, hits)):
            if delta.text:
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - start) * 1000
                yield _event("delta", {"text": delta.text})
            if delta.usage:
                usage = delta.usage
    except LLMUnavailableError as exc:
        logger.error("ask failed: %s", exc)
        yield _event(
            "error", {"message": "El modelo no está disponible ahora. Intenta en un momento."}
        )
        return

    metrics = {
        "model": llm.model,
        "retrieval_ms": round(retrieval_ms),
        "first_token_ms": round(first_token_ms) if first_token_ms is not None else None,
        "total_ms": round(retrieval_ms + (time.perf_counter() - start) * 1000),
        "input_tokens": usage.input_tokens if usage else None,
        "output_tokens": usage.output_tokens if usage else None,
        "llm_called": True,
    }
    # Una línea por pregunta con latencia y tokens: lo mínimo para saber cuánto cuesta y dónde se va el tiempo.
    logger.info("ask %s", json.dumps(metrics))
    yield _event("done", metrics)
