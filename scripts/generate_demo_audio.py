"""Explicit, bounded one-time asset generation; never used by the public frontend."""
import argparse
import json
import logging
from pathlib import Path
import shutil
import sys
import tempfile
from io import BytesIO
import wave

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "frontend/src/demo/sample.json"
OUTPUT = ROOT / "frontend/public/demo/audio"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true", help="Make paid TTS calls using the existing backend configuration.")
    args = parser.parse_args()
    scene = json.loads(SAMPLE.read_text())
    lines = scene["lines"]
    if len(lines) != 8 or len(scene["characters"]) != 2:
        print("Expected the approved two-character, eight-turn sample. No calls made.")
        return 1
    if not args.generate:
        print("Dry run: 8 sequential TTS calls, one per line, covering both characters. No parsing calls or automatic retries.")
        print("Add --generate to create the prepared audio. No credentials were loaded.")
        return 0
    if OUTPUT.exists():
        print("Audio output already exists. Refusing to overwrite it or make paid calls.")
        return 1

    # Import only after explicit --generate. Credentials stay inside the existing service.
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import get_character_voice
    from app.services.speech import OpenAISpeechService

    try:
        for index in range(2):
            get_character_voice(index, "any")  # Validate the palette before spending.
        service = OpenAISpeechService()
        # Do not expose provider diagnostics through this asset-generation command.
        logging.disable(logging.CRITICAL)
        with tempfile.TemporaryDirectory(prefix="scene-demo-") as temporary:
            staging = Path(temporary)
            for line in lines:
                index = scene["characters"].index(line["character"])
                audio = service.generate(line["text"], index, "any")
                with wave.open(BytesIO(audio), "rb") as source:
                    if not source.getnframes() or not source.readframes(1):
                        raise ValueError("Empty audio")
                (staging / f"line-{line['id']}.wav").write_bytes(audio)
                print(f"Prepared line {line['id']} of 8.")
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging, OUTPUT)
        print("Prepared all 8 files. Listen to every line in both roles before publishing.")
        return 0
    except Exception:
        print("Generation stopped. Earlier calls may have been billed; no automatic retry was made. Check backend configuration before running again.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
