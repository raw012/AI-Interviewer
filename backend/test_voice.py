"""Voice resolution: self-hosted Kokoro first, hosted fallback, voices tied to faces."""

import os
import tempfile

# Importing voice pulls in storage; keep tests away from the real database.
os.environ.setdefault("AI_INTERVIEWER_DB", os.path.join(tempfile.mkdtemp(), "voice-test.db"))

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import local_tts
import voice
from knowledge import PERSONAS, VOICES, persona_key


class SpecTests(TestCase):
    def test_single_voice(self):
        self.assertEqual(local_tts.parse_spec("af_sarah"), ([("af_sarah", 1.0)], 1.0))

    def test_blend_and_speed(self):
        parts, speed = local_tts.parse_spec("af_kore*0.7+zf_xiaoxiao*0.3@0.95")
        self.assertEqual([n for n, _ in parts], ["af_kore", "zf_xiaoxiao"])
        self.assertAlmostEqual(sum(w for _, w in parts), 1.0)
        self.assertEqual(speed, 0.95)

    def test_rejects_bad_speed(self):
        with self.assertRaises(ValueError):
            local_tts.parse_spec("af_sarah@3")


class ResolveTests(TestCase):
    def test_default_is_kokoro_when_installed(self):
        with patch("local_tts.available", return_value=True):
            self.assertEqual(voice.resolve_voice("grace", "auto"), ("kokoro", PERSONAS["grace"]["voices"]["kokoro"]))

    def test_falls_back_to_groq_without_model(self):
        with patch("local_tts.available", return_value=False):
            self.assertEqual(voice.resolve_voice("daniel", "auto"), ("groq", "daniel"))

    def test_voice_for_another_face_is_replaced(self):
        with patch("local_tts.available", return_value=True):
            provider, chosen = voice.resolve_voice("david", "kokoro:af_sarah")
        self.assertEqual((provider, chosen), ("kokoro", PERSONAS["david"]["voices"]["kokoro"]))

    def test_matching_alternate_is_kept(self):
        self.assertEqual(voice.resolve_voice("maya", "kokoro:af_heart"), ("kokoro", "af_heart"))

    def test_old_persona_keys_map_to_new_ones(self):
        self.assertEqual(persona_key("priya"), "grace")
        self.assertEqual(persona_key("alex"), "david")
        self.assertEqual(persona_key("unknown"), "maya")

    def test_every_default_and_alternate_is_listed_for_its_persona(self):
        for key, persona in PERSONAS.items():
            for spec in [persona["voices"]["kokoro"], *persona["voices"]["kokoro_alt"]]:
                self.assertTrue(voice._suits(f"kokoro:{spec}", key), f"{key}: {spec}")

    def test_kokoro_failure_uses_hosted_voice(self):
        with patch("local_tts.available", return_value=True), \
             patch("local_tts.synthesize", side_effect=RuntimeError("boom")), \
             patch("voice.optional_voice_key", return_value="key"), \
             patch("voice.synthesize_voice", return_value=(b"x", "audio/wav", "groq:troy")) as hosted, \
             patch("voice.CACHE_DIR", Path(tempfile.mkdtemp())):
            audio, _, used = voice.speak("u1", "Hello there, unique line 9f2", "david", "auto")
        self.assertEqual(used, "groq:troy")
        self.assertEqual(hosted.call_args.args[1:3], ("groq", "troy"))


class CatalogueTests(TestCase):
    def test_voice_ids_are_unique(self):
        ids = [v["id"] for v in VOICES]
        self.assertEqual(len(ids), len(set(ids)))
