from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIStatusError

from app.main import app
from app.config import TTS_READER_INSTRUCTIONS, get_character_voice
from app.services.speech import OpenAISpeechService, SpeechGenerationError, get_speech_service


@pytest.fixture
def service():
    fake = MagicMock()
    fake.generate.return_value = b"mock wav bytes"
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
    assert response.content == b"mock wav bytes"
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    service.generate.assert_called_once_with("Hello.", 0)


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
    monkeypatch.setenv("OPENAI_TTS_VOICES", "marin,cedar,coral,ash")
    factory = MagicMock()
    monkeypatch.setattr("app.services.speech.OpenAI", factory)
    return factory


def test_openai_speech_uses_configuration_and_wav(openai_client):
    client = openai_client.return_value.__enter__.return_value
    client.audio.speech.create.return_value = SimpleNamespace(content=b"audio")
    assert OpenAISpeechService().generate("Hello.") == b"audio"
    openai_client.assert_called_once_with(api_key="test-only", timeout=30.0, max_retries=0)
    client.audio.speech.create.assert_called_once_with(
        model="test-tts", voice="marin", input="Hello.", response_format="wav",
        instructions=TTS_READER_INSTRUCTIONS,
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


def test_voice_assignment_is_stable_distinct_and_wraps(monkeypatch):
    monkeypatch.setenv("OPENAI_TTS_VOICE", "cedar")
    monkeypatch.setenv("OPENAI_TTS_VOICES", "marin, cedar,coral,marin")
    assert [get_character_voice(i) for i in range(5)] == ["cedar", "marin", "coral", "cedar", "marin"]
    assert get_character_voice(1) == get_character_voice(1)


def test_invalid_voice_configuration_is_controlled(monkeypatch):
    monkeypatch.setenv("OPENAI_TTS_VOICES", "unknown")
    with pytest.raises(RuntimeError):
        get_character_voice(0)


@pytest.mark.parametrize("index", [-1, 1.5, "1", True])
def test_invalid_voice_index_never_calls_service(service, index):
    response = TestClient(app).post("/api/speech", json={"text": "Hello.", "voice_index": index})
    assert response.status_code == 422
    service.generate.assert_not_called()


def test_endpoint_passes_character_index(service):
    response = TestClient(app).post("/api/speech", json={"text": "Hello.", "voice_index": 2})
    assert response.status_code == 200
    service.generate.assert_called_once_with("Hello.", 2)


def test_service_uses_assigned_voice(openai_client):
    client = openai_client.return_value.__enter__.return_value
    client.audio.speech.create.return_value = SimpleNamespace(content=b"audio")
    OpenAISpeechService().generate("Hello.", 1)
    assert client.audio.speech.create.call_args.kwargs["voice"] == "cedar"


@pytest.mark.parametrize("status, code, retryable", [
    (400, "invalid_request", False), (401, "invalid_api_key", False),
    (429, "insufficient_quota", False), (429, "rate_limit_exceeded", True),
    (500, "server_error", True), (503, "server_error", True),
])
def test_provider_errors_expose_retry_classification_and_safe_logs(openai_client, caplog, status, code, retryable):
    client = openai_client.return_value.__enter__.return_value
    client.audio.speech.create.side_effect = APIStatusError(
        "private provider body", body={"code": code},
        response=httpx.Response(status, headers={"x-request-id": "req-test"}, request=httpx.Request("POST", "https://example.test")),
    )
    response = TestClient(app).post("/api/speech", json={"text": "Private dialogue"})
    assert response.status_code == 502
    assert response.headers["x-speech-retryable"] == str(retryable).lower()
    assert "req-test" in caplog.text
    assert code in caplog.text
    assert "Private dialogue" not in caplog.text
    assert "private provider body" not in caplog.text
    client.audio.speech.create.assert_called_once()


def test_missing_configuration_is_not_retryable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).post("/api/speech", json={"text": "Hello."})
    assert response.status_code == 503
    assert response.headers["x-speech-retryable"] == "false"


def test_realistic_provider_wav_survives_full_speech_endpoint(openai_client):
    from io import BytesIO
    import struct
    import wave

    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(24000)
        target.writeframes(struct.pack("<24000h", *([1000] * 2400 + [0] * 21600)))
    provider_audio = bytearray(output.getvalue())
    struct.pack_into("<I", provider_audio, 4, 0xffffffff)
    struct.pack_into("<I", provider_audio, 40, 0xffffffff)
    client = openai_client.return_value.__enter__.return_value
    client.audio.speech.create.return_value = SimpleNamespace(content=bytes(provider_audio))
    response = TestClient(app).post("/api/speech", json={"text": "Hello.", "voice_index": 1})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    with wave.open(BytesIO(response.content), "rb") as audio:
        assert audio.getnframes() == 6000
    client.audio.speech.create.assert_called_once()
