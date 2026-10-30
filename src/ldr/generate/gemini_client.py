import logging
import random
import time
from collections.abc import Iterator

import httpx
from google import genai
from google.genai import errors, types

from ldr.generate.llm import Delta, LLMUnavailableError, Usage

logger = logging.getLogger(__name__)

# 429 = te pasaste del límite de requests (muy común en el free tier); 500/503/504 = el servicio falló,
# está saturado o no alcanzó a responder. Los demás (400 request mal armado, 403 key inválida) no se
# arreglan reintentando.
RETRYABLE = {429, 500, 503, 504}


def _failure(exc: Exception) -> tuple[bool, str]:
    """(¿vale la pena reintentar?, descripción corta) de un error de Gemini."""
    if isinstance(exc, errors.APIError):
        return exc.code in RETRYABLE, f"{exc.code} {exc.status}"
    if isinstance(exc, httpx.TimeoutException):
        return True, "timeout"
    raise exc


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 30.0,
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self.model = model
        # Sin timeout, un modelo que no responde deja el request colgado para siempre.
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._config = types.GenerateContentConfig(
            temperature=0.2,  # baja: queremos fidelidad a las fuentes, no creatividad
            # Los modelos 3.x "piensan" antes de responder. Para responder con contexto ya dado basta
            # poco razonamiento, y cada token pensado suma latencia y cuota.
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )

    def stream(self, system: str, user: str) -> Iterator[Delta]:
        config = self._config.model_copy(update={"system_instruction": system})
        chunks = self._open_stream(user, config)
        usage = None
        try:
            for chunk in chunks:
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata
                if chunk.text:
                    yield Delta(text=chunk.text)
        except (errors.APIError, httpx.TimeoutException) as exc:
            # A mitad de la respuesta ya no se puede reintentar: el usuario ya vio una parte.
            raise LLMUnavailableError(f"Gemini cortó la respuesta: {_failure(exc)[1]}") from exc
        if usage:
            yield Delta(
                usage=Usage(usage.prompt_token_count or 0, usage.candidates_token_count or 0)
            )

    def _open_stream(
        self, user: str, config: types.GenerateContentConfig
    ) -> Iterator[types.GenerateContentResponse]:
        """Abre el stream con reintentos y backoff exponencial con jitter: 1 s, 2 s, ... (± azar).

        El jitter evita que muchos clientes que fallaron a la vez reintenten todos en el mismo instante.
        El error, si ocurre, llega al pedir el PRIMER pedazo: por eso se reintenta hasta obtenerlo.
        """
        for attempt in range(1, self._max_attempts + 1):
            stream = self._client.models.generate_content_stream(
                model=self.model, contents=user, config=config
            )
            try:
                first = next(stream)
            except StopIteration:
                return iter(())
            except (errors.APIError, httpx.TimeoutException) as exc:
                retryable, reason = _failure(exc)
                if not retryable or attempt == self._max_attempts:
                    raise LLMUnavailableError(
                        f"Gemini no respondió ({self.model}): {reason}"
                    ) from exc
                delay = self._base_delay * 2 ** (attempt - 1) * random.uniform(0.75, 1.25)  # noqa: S311
                logger.warning("gemini %s, reintento %d en %.1fs", reason, attempt, delay)
                time.sleep(delay)
                continue
            return _prepend(first, stream)
        raise AssertionError("unreachable")


def _prepend(first, rest):
    yield first
    yield from rest
