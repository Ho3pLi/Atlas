"""Exercise the installed SDKs against HTTP transports with synthetic responses."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from atlas import config, core, screenshot


class ProviderCompatibilityTests(unittest.TestCase):
    def test_groq_routing_chat_and_summary_use_configured_models(self):
        from groq import Groq

        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            if body.get("response_format"):
                content = '{"action":"none","confidence":0.9,"needs_clarification":false,"reason":"small_talk"}'
            else:
                content = "synthetic response"
            return httpx.Response(
                200,
                json={
                    "id": "synthetic",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                },
            )

        with (
            httpx.Client(transport=httpx.MockTransport(respond)) as http_client,
            Groq(api_key="synthetic-key", http_client=http_client) as client,
            patch.object(config, "get_groq_client", return_value=client),
            patch.object(config, "session", config.SessionState()),
            patch.object(config.app, "groq_model", "openai/gpt-oss-20b"),
            patch.object(config.app, "groq_model2", "openai/gpt-oss-120b"),
        ):
            config.reset_conversation()
            self.assertFalse(
                core.functionCall("unclassified sentence")["needs_clarification"]
            )
            self.assertEqual(core.groqPrompt("short"), "synthetic response")
            self.assertEqual(core.groqPrompt("long " * 30), "synthetic response")
            self.assertEqual(
                core._summarize_messages([{"role": "user", "content": "synthetic"}]),
                "synthetic response",
            )
        self.assertEqual(
            [body["model"] for body in requests],
            [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
            ],
        )
        self.assertEqual(requests[0]["response_format"], {"type": "json_object"})

    def test_google_genai_serializes_image_config_and_custom_model(self):
        from google import genai

        real_client = genai.Client
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": "synthetic image description"}],
                            },
                            "finishReason": "STOP",
                        }
                    ]
                },
            )

        def local_client(**kwargs):
            return real_client(
                **kwargs,
                http_options={
                    "client_args": {"transport": httpx.MockTransport(respond)}
                },
            )

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "synthetic.png")
            with Image.new("RGB", (4, 4), "red") as image:
                image.save(path)
            with (
                patch.object(genai, "Client", side_effect=local_client),
                patch.object(config.app, "google_api_key", "synthetic-key"),
                patch.object(config.app, "gemini_model", "gemini-3.8-flash"),
                patch.object(config, "_gemini_model", None),
            ):
                self.assertEqual(
                    screenshot.visionPrompt("synthetic prompt", str(path)),
                    "synthetic image description",
                )
            # A closed image can be replaced on Windows immediately after the call.
            path.unlink()
        self.assertEqual(len(requests), 1)
        self.assertIn("gemini-3.8-flash:generateContent", str(requests[0].url))
        body = json.loads(requests[0].content)
        self.assertTrue(
            any("inlineData" in part for part in body["contents"][0]["parts"])
        )
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 2048)


if __name__ == "__main__":
    unittest.main()
