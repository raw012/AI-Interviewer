"""Check that Qwen region choices send requests to matching endpoints."""

from unittest import TestCase
from unittest.mock import Mock, patch

from providers import complete_text


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
