from io import BytesIO
import struct
import wave

import pytest

from app.services.audio import trim_silent_tail


def wav_bytes(samples, channels=1, width=2):
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(1000)
        target.writeframes(struct.pack(f"<{len(samples)}h", *samples) if width == 2 else bytes(samples))
    return output.getvalue()


def read_samples(audio):
    with wave.open(BytesIO(audio), "rb") as source:
        frames = source.readframes(source.getnframes())
        return struct.unpack(f"<{len(frames)//2}h", frames)


def test_trim_only_tail_keeps_quiet_ending_and_internal_pause():
    spoken = [1000] * 100 + [0] * 700 + [40] * 50
    audio = wav_bytes(spoken + [0] * 1000)
    assert read_samples(trim_silent_tail(audio)) == tuple(spoken + [0] * 150)


def test_stereo_preserves_speech_on_either_channel():
    spoken = [0, 1000] * 100
    assert read_samples(trim_silent_tail(wav_bytes(spoken + [0, 0] * 800, channels=2))) == tuple(spoken + [0, 0] * 150)


@pytest.mark.parametrize("samples", [[1000] * 100 + [0] * 200, [0] * 1000, [100] * 500])
def test_short_tail_silence_and_unbroken_audio_unchanged(samples):
    audio = wav_bytes(samples)
    assert trim_silent_tail(audio) == audio


def test_unsupported_and_invalid_audio_unchanged():
    for audio in [b"invalid", wav_bytes([128] * 1000, width=1)]:
        assert trim_silent_tail(audio) == audio


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("tail", [100, 1000])
def test_provider_unknown_length_headers_use_actual_frames(channels, tail):
    samples = [1000] * 100 * channels + [0] * tail * channels
    audio = bytearray(wav_bytes(samples, channels=channels))
    # Reproduce OpenAI WAVs: the downloaded data is finite, the header is not.
    struct.pack_into("<I", audio, 4, 0xffffffff)
    struct.pack_into("<I", audio, 40, 0xffffffff)
    result = trim_silent_tail(bytes(audio))
    expected_frames = 250 if tail >= 300 else 100 + tail
    with wave.open(BytesIO(result), "rb") as source:
        assert source.getnframes() == expected_frames
        assert source.getnchannels() == channels
    assert struct.unpack_from("<I", result, 4)[0] == len(result) - 8
    assert read_samples(result) == tuple(samples[:expected_frames * channels])


def test_optional_processing_error_returns_original_audio(monkeypatch):
    audio = wav_bytes([1000] * 100 + [0] * 1000)
    def fail_write(*args):
        raise struct.error("simulated writer failure")
    monkeypatch.setattr(wave.Wave_write, "writeframes", fail_write)
    assert trim_silent_tail(audio) == audio
