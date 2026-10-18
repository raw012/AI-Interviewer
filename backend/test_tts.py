"""Exercise question speech, Groq chunking, and ElevenLabs failover offline."""

from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch
import wave

import httpx

from providers import synthesize_question, test_provider


def sample_wav() -> bytes:
    """Return a small valid WAV payload for deterministic tests."""
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 100)
    return output.getvalue()


class QuestionSpeechTests(TestCase):
    """Fail over only when Groq is rate-limited or unavailable."""

    def test_groq_uses_orpheus_english(self):
        response = Mock(status_code=200, content=sample_wav())
        with patch("providers.httpx.post", return_value=response) as request:
            audio, media_type, provider = synthesize_question("Tell me about yourself.", "groq-key", None)
        self.assertEqual((audio, media_type, provider), (response.content, "audio/wav", "groq"))
        self.assertEqual(request.call_args.kwargs["json"]["model"], "canopylabs/orpheus-v1-english")

    def test_long_question_is_split_and_wav_is_joined(self):
        response = Mock(status_code=200, content=sample_wav())
        with patch("providers.httpx.post", return_value=response) as request:
            audio, _, provider = synthesize_question("A question with several words. " * 12, "groq-key", None)
        self.assertGreater(request.call_count, 1)
        self.assertTrue(all(len(call.kwargs["json"]["input"]) <= 200 for call in request.call_args_list))
        with wave.open(BytesIO(audio), "rb") as joined:
            self.assertEqual(joined.getnframes(), 100 * request.call_count)
        self.assertEqual(provider, "groq")

    def test_groq_limit_uses_elevenlabs_flash(self):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/speech")
        limited = httpx.Response(429, request=request)
        groq = Mock()
        groq.raise_for_status.side_effect = httpx.HTTPStatusError("limited", request=request, response=limited)
        elevenlabs = Mock(status_code=200, content=b"mp3-audio")
        with patch("providers.httpx.post", side_effect=[groq, elevenlabs]) as post:
            audio, media_type, provider = synthesize_question("Explain a trade-off.", "groq-key", "eleven-key")
        self.assertEqual((audio, media_type, provider), (b"mp3-audio", "audio/mpeg", "elevenlabs"))
        self.assertEqual(post.call_args.kwargs["json"]["model_id"], "eleven_flash_v2_5")
        self.assertEqual(post.call_args.kwargs["headers"], {"xi-api-key": "eleven-key"})

    def test_groq_server_outage_uses_elevenlabs(self):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/speech")
        unavailable = httpx.Response(503, request=request)
        groq = Mock()
        groq.raise_for_status.side_effect = httpx.HTTPStatusError("unavailable", request=request, response=unavailable)
        with patch("providers.httpx.post", side_effect=[groq, Mock(content=b"backup-mp3")]):
            _, _, provider = synthesize_question("Another question?", "groq-key", "eleven-key")
        self.assertEqual(provider, "elevenlabs")

    def test_elevenlabs_can_read_without_a_groq_key(self):
        with patch("providers.httpx.post", return_value=Mock(content=b"mp3-audio")) as post:
            _, _, provider = synthesize_question("Question?", None, "eleven-key")
        self.assertEqual(provider, "elevenlabs")
        self.assertEqual(post.call_count, 1)

    def test_invalid_groq_key_does_not_spend_backup_credits(self):
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/speech")
        unauthorized = httpx.Response(401, request=request)
        groq = Mock()
        groq.raise_for_status.side_effect = httpx.HTTPStatusError("invalid", request=request, response=unauthorized)
        with patch("providers.httpx.post", return_value=groq) as post:
            with self.assertRaises(httpx.HTTPStatusError):
                synthesize_question("Question?", "bad-key", "eleven-key")
        self.assertEqual(post.call_count, 1)

    def test_elevenlabs_key_check_generates_only_a_short_probe(self):
        response = Mock(status_code=200, content=b"sample-mp3")
        with patch("providers.httpx.post", return_value=response) as post:
            test_provider("elevenlabs", "eleven-key")
        self.assertIn("/v1/text-to-speech/", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["text"], "Ready.")
