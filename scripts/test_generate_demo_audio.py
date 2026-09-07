"""Offline checks: replace the entire backend service before exercising generation."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

spec = importlib.util.spec_from_file_location("generate_demo_audio", Path(__file__).with_name("generate_demo_audio.py"))
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class GenerationTests(unittest.TestCase):
    def test_explicit_generation_uses_eight_fixed_slots_and_refuses_overwrite(self):
        calls = []
        data = io.BytesIO()
        with wave.open(data, "wb") as target:
            target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            target.writeframes(bytes(320))

        class FakeSpeech:
            def generate(self, text, index, category):
                calls.append((text, index, category))
                return data.getvalue()

        config = types.ModuleType("app.config")
        config.get_character_voice = lambda index, category: "fake"
        speech = types.ModuleType("app.services.speech")
        speech.OpenAISpeechService = FakeSpeech
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "audio"
            with patch.object(generator, "OUTPUT", output), patch.object(sys, "argv", ["generate", "--generate"]), patch.dict(sys.modules, {"app.config": config, "app.services.speech": speech}), patch("logging.disable"), patch("builtins.print"):
                self.assertEqual(generator.main(), 0)
                self.assertEqual(len(list(output.glob("*.wav"))), 8)
                self.assertEqual([call[1] for call in calls], [0, 1] * 4)
                self.assertTrue(all(call[2] == "any" for call in calls))
                self.assertEqual(generator.main(), 1)
                self.assertEqual(len(calls), 8)

    def test_dry_run_never_imports_backend(self):
        with patch.object(sys, "argv", ["generate"]), patch.dict(sys.modules, {"app.config": None, "app.services.speech": None}), patch("builtins.print"):
            self.assertEqual(generator.main(), 0)


if __name__ == "__main__":
    unittest.main()
