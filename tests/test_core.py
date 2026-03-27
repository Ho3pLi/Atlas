import unittest
from unittest.mock import patch

import atlas.config as config
from atlas import core


class CoreRoutingTests(unittest.TestCase):
    def setUp(self):
        config.reset_conversation()
        self.original_aliases = dict(config.app.app_aliases)
        config.app.app_aliases = {**self.original_aliases, "medal": "medal.exe"}

    def tearDown(self):
        config.app.app_aliases = self.original_aliases

    def test_heuristic_weather_routing(self):
        intent = core.functionCall("Che meteo fa domani a Roma?")

        self.assertEqual(intent["action"], "get_weather")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_ambiguous_prompt_requests_clarification(self):
        intent = core.functionCall("tempo schermata")

        self.assertEqual(intent["action"], "none")
        self.assertTrue(intent["needs_clarification"])
        self.assertEqual(intent["reason"], "ambiguous_heuristic_match")

    def test_heuristic_open_app_routing(self):
        intent = core.functionCall("Avvia Chrome")

        self.assertEqual(intent["action"], "open_app")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_open_app_alias_routing(self):
        intent = core.functionCall("apri medal")

        self.assertEqual(intent["action"], "open_app")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_close_app_alias_routing(self):
        intent = core.functionCall("chiudi discord")

        self.assertEqual(intent["action"], "close_app")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_get_date_routing(self):
        intent = core.functionCall("Che giorno e oggi?")

        self.assertEqual(intent["action"], "get_date")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_get_time_routing(self):
        intent = core.functionCall("che ora e")

        self.assertEqual(intent["action"], "get_time")
        self.assertEqual(intent["source"], "heuristic")
        self.assertFalse(intent["needs_clarification"])

    def test_heuristic_capabilities_prompt_as_small_talk(self):
        intent = core.functionCall("cosa puoi fare")

        self.assertEqual(intent["action"], "none")
        self.assertEqual(intent["reason"], "capabilities_query")
        self.assertFalse(intent["needs_clarification"])
        self.assertEqual(intent["source"], "heuristic")

    def test_validate_intent_downgrades_low_confidence_action(self):
        result = core._validate_intent(
            {
                "action": "search_file",
                "confidence": 0.2,
                "needs_clarification": False,
                "reason": "weak_guess",
                "source": "llm",
            }
        )

        self.assertEqual(result["action"], "none")
        self.assertTrue(result["needs_clarification"])

    def test_heuristic_small_talk_does_not_require_clarification(self):
        intent = core.functionCall("Ciao, come va?")

        self.assertEqual(intent["action"], "none")
        self.assertEqual(intent["reason"], "small_talk")
        self.assertFalse(intent["needs_clarification"])
        self.assertEqual(intent["source"], "heuristic")

    def test_validate_intent_caps_none_confidence_for_unknown_intent(self):
        result = core._validate_intent(
            {
                "action": "none",
                "confidence": 1.0,
                "needs_clarification": True,
                "reason": "unknown intent",
                "source": "llm",
            }
        )

        self.assertEqual(result["action"], "none")
        self.assertTrue(result["needs_clarification"])
        self.assertLessEqual(result["confidence"], 0.4)

    @patch("atlas.core._summarize_messages", return_value="summary memory")
    def test_conversation_trim_keeps_recent_messages_and_summary(self, summarize_mock):
        config.app.max_recent_conversation_messages = 2
        config.app.conversation_summary_trigger = 3
        config.reset_conversation()
        config.session.conversation.extend(
            [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
            ]
        )

        core._trim_conversation_if_needed()

        self.assertEqual(config.session.conversation_summary, "summary memory")
        self.assertEqual(config.session.conversation[1:], [{"role": "user", "content": "u2"}, {"role": "assistant", "content": "a2"}])
        summarize_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
