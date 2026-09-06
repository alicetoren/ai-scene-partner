from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.main import app
from app.services.speech import OpenAISpeechService, SpeechGenerationError, get_speech_service


@pytest.fixture
def service():
    fake = MagicMock()
    fake.generate.return_value = b"mock mp3 bytes"
    app.dependency_overrides[get_speech_service] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": " \n\t"}, {}, {"text": 123}, {"text": "x" * 4097}, {"text": "Hello", "voice": "alloy"}])
def test_invalid_text_does_not_call_speech_service(service, payload):
    response = TestClient(app).post("/api/speech", json=payload)
    assert response.status_code == 422
    service.generate.assert_not_called()


def test_speech_returns_audio_without_storage(service):
    response = TestClient(app).post("/api/speech", json={"text": " Hello. "})
    assert response.status_code == 200
    assert response.content == b"mock mp3 bytes"
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store"
    service.generate.assert_called_once_with("Hello.")


@pytest.mark.parametrize("error, code, detail", [
    (SpeechGenerationError("private provider details"), 502, "Speech generation failed. Please retry this line."),
    (RuntimeError("private configuration details"), 503, "Speech is not configured on the server."),
])
def test_speech_failure_is_controlled(service, error, code, detail):
    service.generate.side_effect = error
    response = TestClient(app).post("/api/speech", json={"text": "Hello."})
    assert response.status_code == code
    assert response.json() == {"detail": detail}


@pytest.fixture
def openai_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("OPENAI_TTS_MODEL", "test-tts")
    monkeypatch.setenv("OPENAI_TTS_VOICE", "marin")
    factory = MagicMock()
    monkeypatch.setattr("app.services.speech.OpenAI", factory)
    return factory


def test_openai_speech_uses_configuration_and_mp3(openai_client):
    client = openai_client.return_value.__enter__.return_value
    client.audio.speech.create.return_value = SimpleNamespace(content=b"audio")
    assert OpenAISpeechService().generate("Hello.") == b"audio"
    openai_client.assert_called_once_with(api_key="test-only", timeout=30.0, max_retries=0)
    client.audio.speech.create.assert_called_once_with(
        model="test-tts", voice="marin", input="Hello.", response_format="mp3",
    )
    openai_client.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("empty_response", [False, True])
def test_openai_failure_is_wrapped(openai_client, empty_response):
    client = openai_client.return_value.__enter__.return_value
    if empty_response:
        client.audio.speech.create.return_value = SimpleNamespace(content=b"")
    else:
        client.audio.speech.create.side_effect = APIConnectionError(request=httpx.Request("POST", "https://example.test"))
    with pytest.raises(SpeechGenerationError):
        OpenAISpeechService().generate("Hello.")
