"""Check that Qwen region choices send requests to matching endpoints."""

from unittest import TestCase
from unittest.mock import Mock, patch

import httpx

from providers import complete_text, test_provider, verification_failure_message


class QwenProviderTests(TestCase):
    """Provider adapter tests without outbound API calls."""

    def test_qwen_regions_use_their_matching_endpoints(self):
        """Both Qwen regions use the same model at distinct URLs."""
        endpoints = {
            "qwen_cn": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "qwen_intl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        }
        for provider, endpoint in endpoints.items():
            with self.subTest(provider=provider):
                response = Mock()
                response.json.return_value = {
                    "choices": [{"message": {"content": " connected "}}]
                }
                with patch("providers.httpx.post", return_value=response) as request:
                    self.assertEqual(complete_text(provider, "test-key", "hi"), "connected")
                self.assertEqual(request.call_args.args[0], endpoint)
                self.assertEqual(request.call_args.kwargs["json"]["model"], "qwen-plus")


class ProviderVerificationTests(TestCase):
    """Keep model checks and safe error messages stable without real keys."""

    def test_groq_verification_uses_supported_model(self):
        """A valid Groq key must not be rejected by a retired model ID."""
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "connected"}}]
        }
        with patch("providers.httpx.post", return_value=response) as request:
            test_provider("groq", "fake-key")
        self.assertEqual(
            request.call_args.kwargs["json"]["model"], "openai/gpt-oss-120b"
        )

    def test_verification_rejects_empty_response(self):
        """An empty model response is not a successful connection test."""
        with patch("providers.complete_text", return_value=""):
            with self.assertRaises(ValueError):
                test_provider("groq", "fake-key")

    def test_upstream_errors_are_classified_without_leaking_secrets(self):
        """Show actionable failures while never returning upstream bodies or keys."""
        request = httpx.Request(
            "POST", "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer sensitive-test-secret"},
        )
        cases = {
            401: "rejected this API key",
            402: "no available credits",
            403: "denied access",
            404: "configured model or request",
            429: "rate-limiting",
            503: "temporarily unavailable",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                response = httpx.Response(
                    status, request=request, text="sensitive-test-secret"
                )
                error = httpx.HTTPStatusError(
                    "upstream failure", request=request, response=response
                )
                message = verification_failure_message("groq", error)
                self.assertIn(expected, message)
                self.assertNotIn("sensitive-test-secret", message)
