import json

import pytest
from fastapi.testclient import TestClient
from test_pipeline import ERRORS_DOC, QUERY_DOC

from ldr.api.main import Services, app, get_db, get_services
from ldr.generate.llm import Delta, LLMUnavailableError, Usage
from ldr.generate.prompts import NO_ANSWER
from ldr.ingest.pipeline import ingest


class FakeLLM:
    model = "fake-llm"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def stream(self, system: str, user: str):
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError("down")
        yield Delta(text="Usa `None` como valor por defecto ")
        yield Delta(text="[1].")
        yield Delta(usage=Usage(200, 12))


def parse_sse(body: str) -> list[tuple[str, object]]:
    events = []
    for block in body.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def client(conn, embedder):
    """La API con la BD de pruebas, el embedder falso y un LLM falso (no se llama a Gemini)."""
    llm = FakeLLM()
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_services] = lambda: Services(embedder, None, llm)
    yield TestClient(app), llm
    app.dependency_overrides.clear()


def test_ask_streams_sources_then_text_then_metrics(client, conn, embedder) -> None:
    http, _llm = client
    ingest(conn, [QUERY_DOC, ERRORS_DOC], embedder, ["markdown"])
    response = http.post("/ask", json={"question": "how to make a query parameter optional?"})

    assert response.status_code == 200
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "sources" and names[-1] == "done"
    assert (
        "".join(d["text"] for n, d in events if n == "delta")
        == "Usa `None` como valor por defecto [1]."
    )
    assert events[0][1][0]["url"].startswith("https://example.test/tutorial/")
    assert events[-1][1]["input_tokens"] == 200


def test_ask_without_sources_does_not_call_the_llm(client) -> None:
    http, llm = client  # base vacía: no hay nada que recuperar
    events = parse_sse(http.post("/ask", json={"question": "anything at all?"}).text)

    assert llm.calls == 0
    assert ("delta", {"text": NO_ANSWER}) in events


def test_llm_failure_becomes_an_error_event(client, conn, embedder) -> None:
    http, llm = client
    llm.fail = True
    ingest(conn, [QUERY_DOC], embedder, ["markdown"])
    events = parse_sse(http.post("/ask", json={"question": "query parameter optional"}).text)

    assert events[-1][0] == "error"


def test_ask_validates_the_request(client) -> None:
    http, _llm = client

    assert http.post("/ask", json={"question": "hi"}).status_code == 422  # muy corta
    assert http.post("/ask", json={"question": "valid question", "k": 50}).status_code == 422


def test_ask_without_api_key_is_503(client, embedder) -> None:
    http, _llm = client
    app.dependency_overrides[get_services] = lambda: Services(embedder, None, None)

    assert http.post("/ask", json={"question": "valid question"}).status_code == 503
