import os

from dotenv import load_dotenv


load_dotenv()

DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "marin"
DEFAULT_TTS_VOICES = "marin,cedar,coral,ash"
SUPPORTED_TTS_VOICES = frozenset({
    "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx",
    "sage", "shimmer", "verse", "marin", "cedar",
})
TTS_READER_INSTRUCTIONS = (
    "Read the dialogue exactly as written, as a grounded, natural scene partner. "
    "Use understated delivery at a normal conversational pace, with light, varied "
    "intonation rather than a monotone. Support the actor without imposing a strong "
    "interpretation. Avoid theatrical emphasis, exaggerated emotion, slow delivery, "
    "and unnecessary dramatic pauses. Respect interrupted sentences without adding "
    "words or a long pause at the end."
)


def get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured on the backend.")
    return api_key


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def get_tts_model() -> str:
    return os.getenv("OPENAI_TTS_MODEL", DEFAULT_TTS_MODEL)


def get_tts_voice() -> str:
    return os.getenv("OPENAI_TTS_VOICE", DEFAULT_TTS_VOICE)


def get_character_voice(index: int) -> str:
    """Stable scene character order selects a voice; reuse only after the palette wraps."""
    voices = list(dict.fromkeys([
        get_tts_voice(),
        *(voice.strip() for voice in os.getenv("OPENAI_TTS_VOICES", DEFAULT_TTS_VOICES).split(",") if voice.strip()),
    ]))
    if any(voice not in SUPPORTED_TTS_VOICES for voice in voices):
        raise RuntimeError("Unsupported speech voice configuration.")
    return voices[index % len(voices)]
