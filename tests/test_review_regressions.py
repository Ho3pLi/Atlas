"""Regression coverage for the November repository review, without external services."""

import importlib
import io
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import atlas
from atlas import appLauncher, config, core, fileHandler, orchestrator, weather

meals = importlib.import_module("atlas.buildMealPlan")


def completion(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(role="assistant", content=content))
        ]
    )


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.state_patch = patch.object(config, "session", config.SessionState())
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)
        config.reset_conversation()

    def test_information_and_negation_cannot_execute_app_commands(self):
        for text in (
            "Cosa significa chiudi chrome",
            "non chiudi chrome",
            "spiega come apri chrome",
            "se dico chiudi chrome cosa succede?",
        ):
            with (
                self.subTest(text=text),
                patch.object(
                    core,
                    "_route_with_llm",
                    return_value={
                        "action": "close_app",
                        "confidence": 1,
                        "needs_clarification": False,
                    },
                ),
                patch.object(appLauncher.subprocess, "run") as run,
            ):
                self.assertNotEqual(core.functionCall(text)["action"], "close_app")
                self.assertEqual(
                    appLauncher.handleCloseAppPrompt(text)["status"], "error"
                )
                run.assert_not_called()

    def test_windows_quoted_arguments_reach_real_child_without_quotes(self):
        if sys.platform != "win32":
            self.skipTest("Windows command line parsing")
        target = subprocess.list2cmdline(
            [
                sys.executable,
                "-c",
                "import json,sys;print(json.dumps(sys.argv[1:]))",
                "Profile 1",
                'a"b',
                "C:\\trailing slash\\",
            ]
        )
        parsed = appLauncher._split_command(target)
        result = subprocess.run(parsed, capture_output=True, text=True, check=True)
        self.assertEqual(
            json.loads(result.stdout), ["Profile 1", 'a"b', "C:\\trailing slash\\"]
        )

    def test_structured_alias_arguments_are_preserved(self):
        args = ["app.exe", "--profile", "Profile 1"]
        with (
            patch.object(appLauncher, "_resolve_executable", return_value="app.exe"),
            patch.object(appLauncher.subprocess, "Popen") as launch,
        ):
            self.assertEqual(appLauncher.launchApplication("app", args)["status"], "ok")
            self.assertEqual(launch.call_args.args[0], args)

    def test_cli_prints_response_and_exits_on_eof_or_interrupt(self):
        for ending in (EOFError(), KeyboardInterrupt()):
            with (
                self.subTest(ending=type(ending)),
                patch("builtins.input", side_effect=["che ore sono", ending]),
                patch("sys.stdout", new_callable=io.StringIO) as output,
            ):
                orchestrator.run_debug_loop()
                self.assertIn("ATLAS: Sono le", output.getvalue())

    def test_exact_longer_file_name_beats_short_substring(self):
        files = ["C:/Docs/report.pdf", "C:/Docs/report finale.pdf"]
        self.assertEqual(
            fileHandler.resolveFileChoice("report finale.pdf", files), files[1]
        )
        self.assertEqual(
            fileHandler.resolveFileChoice("apri report finale.pdf", files), files[1]
        )
        self.assertEqual(
            fileHandler.resolveFileChoice("apri report finale", files), files[1]
        )

    def test_duplicate_basename_requires_path_or_number(self):
        files = ["C:/A/report.pdf", "C:/B/report.pdf"]
        with patch.object(config, "get_groq_client") as llm:
            self.assertIsNone(fileHandler.handleFileChoice("report.pdf", files))
            llm.assert_not_called()
        self.assertEqual(
            fileHandler.resolveFileChoice("C:/B/report.pdf", files), files[1]
        )
        self.assertEqual(fileHandler.resolveFileChoice("2", files), files[1])

    def test_digit_in_filename_is_not_selection_number(self):
        files = ["C:/A/one.pdf", "C:/B/report 1.pdf"]
        self.assertEqual(fileHandler.resolveFileChoice("report 1.pdf", files), files[1])

    def test_pending_file_allows_other_commands_and_cancellation(self):
        config.session.last_file_search_results = ["a.txt", "b.txt"]
        with patch.object(config, "get_groq_client") as llm:
            self.assertIn("Sono le", orchestrator.process_user_prompt("che ore sono"))
            self.assertEqual(len(config.session.last_file_search_results), 2)
            self.assertIn(
                "annullata", orchestrator.process_user_prompt("annulla ricerca")
            )
            self.assertEqual(config.session.last_file_search_results, [])
            llm.assert_not_called()

    def test_pending_file_allows_unrelated_conversation(self):
        config.session.last_file_search_results = ["a.txt", "b.txt"]
        with (
            patch.object(
                atlas,
                "functionCall",
                return_value={
                    "action": "none",
                    "confidence": 0.9,
                    "needs_clarification": False,
                    "source": "llm",
                },
            ),
            patch.object(atlas, "groqPrompt", return_value="barzelletta"),
        ):
            self.assertEqual(
                orchestrator.process_user_prompt("raccontami una barzelletta"),
                "barzelletta",
            )
        self.assertEqual(config.session.last_file_search_results, ["a.txt", "b.txt"])

    def test_ambiguous_file_name_still_requests_clarification(self):
        config.session.last_file_search_results = ["C:/A/report.pdf", "C:/B/report.pdf"]
        with patch.object(config, "get_groq_client") as client:
            self.assertIn("nome esatto", orchestrator.process_user_prompt("report.pdf"))
            client.assert_not_called()

    def test_extension_filters_fuzzy_and_semantic_candidates(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in (
                "Report.PDF",
                "Report.docx",
                "report finale.pdf",
                "report finale.docx",
            ):
                Path(folder, name).touch()
            with (
                patch.object(config.app, "allowed_dirs", [folder]),
                patch.object(
                    fileHandler,
                    "extractFileInfo",
                    return_value={"filename": "repor", "extension": ".pdf"},
                ),
                patch.object(
                    fileHandler, "extractSemanticKeywords", return_value=["report"]
                ),
            ):
                self.assertTrue(fileHandler.searchFiles("trova repor pdf"))
                self.assertTrue(
                    all(
                        path.lower().endswith(".pdf")
                        for path in fileHandler.searchFiles("trova repor pdf")
                    )
                )
            self.assertTrue(
                all(
                    path.lower().endswith(".pdf")
                    for path in fileHandler.semanticSearch(
                        ["report"], [folder], extension=".PDF"
                    )
                )
            )

    def test_today_uses_current_endpoint_over_https_with_encoded_params(self):
        payload = {
            "cod": 200,
            "timezone": -18000,
            "weather": [{"description": "sereno"}],
            "main": {"temp": 20},
        }
        with (
            patch.object(config.app, "weather_api_key", "synthetic-key"),
            patch.object(config, "get_groq_client") as client,
            patch.object(weather.requests, "get") as get,
        ):
            client.return_value.chat.completions.create.return_value = completion(
                '{"city":"Rho & test","date":"today"}'
            )
            get.return_value.json.return_value = payload
            result = weather.handleWeatherPrompt("meteo oggi")
            self.assertEqual(result["report"]["source"], "current")
            self.assertEqual(
                get.call_args.args[0], "https://api.openweathermap.org/data/2.5/weather"
            )
            self.assertEqual(get.call_args.kwargs["params"]["q"], "Rho & test")
            self.assertNotIn("synthetic-key", get.call_args.args[0])

    def test_forecast_date_uses_city_timezone(self):
        # 2026-11-07 04:00 UTC is still November 6 at UTC-5.
        from datetime import datetime, timezone

        stamp = int(datetime(2026, 11, 7, 4, tzinfo=timezone.utc).timestamp())
        payload = {
            "cod": "200",
            "city": {"timezone": -18000},
            "list": [
                {
                    "dt": stamp,
                    "main": {"temp": 12},
                    "weather": [{"description": "sereno"}],
                }
            ],
        }
        with (
            patch.object(config.app, "weather_api_key", "synthetic"),
            patch.object(weather.requests, "get") as get,
        ):
            get.return_value.json.return_value = payload
            result = weather.getWeather("New York", date="2026-11-06")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["date"], "2026-11-06")

    def test_router_rejects_invalid_json_types_and_fields(self):
        invalid = [
            {"action": "get_time", "confidence": 10**400, "needs_clarification": False},
            [],
            None,
            "hello",
            {"action": []},
            {"action": "unknown"},
            {
                "action": "get_time",
                "confidence": float("nan"),
                "needs_clarification": False,
            },
            {"action": "get_time", "confidence": 0.9, "needs_clarification": "false"},
            {"action": "get_time", "confidence": True, "needs_clarification": False},
        ]
        for value in invalid:
            with (
                self.subTest(value=value),
                patch.object(config, "get_groq_client") as client,
            ):
                client.return_value.chat.completions.create.return_value = completion(
                    json.dumps(value)
                )
                result = core._validate_intent(core._route_with_llm("unclassified"))
                self.assertEqual(result["action"], "none")
                self.assertTrue(result["needs_clarification"])

    def test_vision_failure_does_not_make_a_contentless_llm_call(self):
        with (
            patch.object(
                atlas,
                "takeScreenshot",
                return_value={"status": "ok", "path": "synthetic.png"},
            ),
            patch.object(atlas, "visionPrompt", return_value=None),
            patch.object(atlas, "groqPrompt") as chat,
        ):
            self.assertIn(
                "non sono riuscito ad analizzarlo",
                orchestrator.process_user_prompt("screenshot"),
            )
            chat.assert_not_called()

    def test_meal_change_routing_has_priority(self):
        self.assertEqual(
            core.functionCall("cambia pasto")["action"], "change_meal_suggestion"
        )

    def preferences(self, count=2):
        config.session.meal_preferences = {key: "nessuno" for key in meals.QUESTIONS}
        config.session.meal_preferences["dailyMealNum"] = str(count)

    def test_meal_counts_select_expected_meals(self):
        for count, expected in meals.MEALS_BY_COUNT.items():
            with (
                self.subTest(count=count),
                patch.object(config, "get_groq_client") as client,
            ):
                self.preferences(count)
                client.return_value.chat.completions.create.return_value = completion(
                    json.dumps({key: "piatto" for key in expected})
                )
                result = meals.askForMeal("Lunedi")
                self.assertEqual(tuple(result), expected)
                self.assertEqual(config.session.meal_plan["Lunedi"], result)
        self.assertEqual(meals.MEALS_BY_COUNT[2], ("pranzo", "cena"))
        self.assertIn("cena", meals.MEALS_BY_COUNT[3])

    def test_bad_meal_response_preserves_previous_plan_and_day(self):
        self.preferences()
        config.session.meal_plan = {"Lunedi": {"pranzo": "old", "cena": "old"}}
        config.session.last_day_planned = "Lunedi"
        for content in (
            "{}",
            '{"pranzo":"x"}',
            '{"pranzo":null,"cena":"x"}',
            "[]",
            "bad json",
        ):
            with (
                self.subTest(content=content),
                patch.object(config, "get_groq_client") as client,
            ):
                client.return_value.chat.completions.create.return_value = completion(
                    content
                )
                with self.assertRaises(ValueError):
                    meals.askForMeal("Martedi")
                self.assertEqual(config.session.last_day_planned, "Lunedi")
                self.assertNotIn("Martedi", config.session.meal_plan)

    def test_invalid_meal_count_does_not_call_service(self):
        for count in (0, 6, "bad"):
            self.preferences(count)
            with patch.object(config, "get_groq_client") as client:
                with self.assertRaises(ValueError):
                    meals.askForMeal("Lunedi")
                client.assert_not_called()

    def test_change_meal_updates_state_and_displays_that_plan(self):
        self.preferences()
        config.session.last_day_planned = "Lunedi"
        config.session.meal_plan = {"Lunedi": {"pranzo": "old", "cena": "old"}}
        new = {"pranzo": "riso", "cena": "zuppa"}
        with (
            patch.object(config, "get_groq_client") as client,
            patch.object(atlas, "groqPrompt") as chat,
        ):
            client.return_value.chat.completions.create.return_value = completion(
                json.dumps(new)
            )
            response = orchestrator.process_user_prompt("cambia pasto")
            self.assertEqual(config.session.meal_plan["Lunedi"], new)
            self.assertIn("pranzo: riso", response)
            self.assertIn("cena: zuppa", response)
            chat.assert_not_called()

    def test_meal_preferences_collected_as_chat_turns_without_stdin(self):
        with (
            patch(
                "builtins.input",
                side_effect=AssertionError("GUI must never read stdin"),
            ),
            patch.object(config, "get_groq_client") as client,
        ):
            self.assertIn(
                "restrizioni", orchestrator.process_user_prompt("piano pasti")
            )
            self.assertIn("Sono le", orchestrator.process_user_prompt("che ore sono"))
            for answer in ("nessuna", "leggeri", "pesce", "riso"):
                orchestrator.process_user_prompt(answer)
            self.assertIn("da 1 a 5", orchestrator.process_user_prompt("9"))
            self.assertIn("diversi", orchestrator.process_user_prompt("due"))
            client.return_value.chat.completions.create.return_value = completion(
                '{"pranzo":"riso","cena":"zuppa"}'
            )
            response = orchestrator.process_user_prompt("si")
            self.assertIn("cena: zuppa", response)
            self.assertEqual(config.session.meal_preferences["foodToAvoid"], "pesce")
            self.assertIsNone(config.session.pending_meal_preferences)

    def test_existing_preferences_are_reused(self):
        self.preferences()
        with (
            patch.object(meals, "setUserMealPlanPref") as collect,
            patch.object(meals, "askForMeal", return_value={}),
        ):
            meals.buildMealPlan("Lunedi")
            collect.assert_not_called()

    def test_fresh_audio_for_each_preference_and_configured_path(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(config.app, "debug_mode", False),
            patch.object(
                config.app, "prompt_path", str(Path(folder, "nested", "answer.wav"))
            ),
            patch.object(config, "get_recognizer") as get_rec,
            patch.object(config, "get_microphone", return_value=MagicMock()),
            patch.object(
                meals,
                "waveToText",
                side_effect=lambda path: Path(path).read_bytes().decode(),
            ),
        ):
            get_rec.return_value.listen.side_effect = [
                SimpleNamespace(get_wav_data=lambda value=str(index): value.encode())
                for index in range(6)
            ]
            self.assertEqual(
                [meals.getVoiceInput() for _ in range(6)],
                [str(index) for index in range(6)],
            )
            self.assertEqual(get_rec.return_value.listen.call_count, 6)
            self.assertFalse(Path(config.app.prompt_path).exists())
            self.assertEqual(
                get_rec.return_value.listen.call_args.kwargs["phrase_time_limit"],
                config.app.phrase_time_limit,
            )

    def test_diagnostics_import_has_no_client_or_secret_output(self):
        with (
            patch("sys.stdout", new_callable=io.StringIO) as output,
            patch.object(config, "get_groq_client") as client,
        ):
            importlib.reload(importlib.import_module("atlas.test"))
            self.assertEqual(output.getvalue(), "")
            client.assert_not_called()

    def test_logs_omit_prompt_and_provider_response(self):
        with (
            patch.object(config, "get_groq_client") as client,
            self.assertLogs(level="INFO") as logs,
        ):
            client.return_value.chat.completions.create.return_value = completion(
                "private-provider-response"
            )
            core.groqPrompt("private-user-prompt")
        self.assertNotIn("private-user-prompt", " ".join(logs.output))
        self.assertNotIn("private-provider-response", " ".join(logs.output))

    def test_log_formatter_redacts_credentials_and_query_keys(self):
        from atlas.logging_utils import RedactingFormatter

        with patch.object(config.app, "google_api_key", "synthetic-secret"):
            record = logging.LogRecord(
                "test",
                logging.ERROR,
                "",
                0,
                "synthetic-secret https://test?appid=another-secret&lang=it",
                (),
                None,
            )
            result = RedactingFormatter().format(record)
            self.assertNotIn("synthetic-secret", result)
            self.assertNotIn("another-secret", result)


class AudioLifetimeTests(unittest.TestCase):
    def resources(self):
        engine = MagicMock(sample_rate=16000, frame_length=1)
        engine.process.return_value = 0
        stream = MagicMock()
        stream.read.return_value = b"\x00\x00"
        pa = MagicMock()
        pa.open.return_value = stream
        return engine, pa, stream

    def test_partial_startup_frees_porcupine(self):
        from atlas import wakeword

        engine, pa, stream = self.resources()
        with (
            patch.dict(
                sys.modules,
                {
                    "pvporcupine": SimpleNamespace(create=Mock(return_value=engine)),
                    "pyaudio": SimpleNamespace(
                        PyAudio=Mock(return_value=pa), paInt16=8
                    ),
                },
            ),
            patch.object(config, "get_recognizer"),
            patch.object(config, "get_microphone", return_value=None),
        ):
            with self.assertRaises(RuntimeError):
                wakeword.startListening(Mock())
        engine.delete.assert_called_once()

    def test_wake_stream_stops_and_microphone_releases_before_callback(self):
        from atlas import wakeword

        engine, pa, stream = self.resources()
        mic = MagicMock()
        recognizer = Mock()

        def callback(audio):
            mic.__exit__.assert_called_once()
            stream.stop_stream.assert_called()
            raise KeyboardInterrupt()

        with (
            patch.dict(
                sys.modules,
                {
                    "pvporcupine": SimpleNamespace(create=Mock(return_value=engine)),
                    "pyaudio": SimpleNamespace(
                        PyAudio=Mock(return_value=pa), paInt16=8
                    ),
                },
            ),
            patch.object(config, "get_recognizer", return_value=recognizer),
            patch.object(config, "get_microphone", return_value=mic),
        ):
            wakeword.startListening(callback)
        self.assertGreater(recognizer.listen.call_args.kwargs["timeout"], 0)
        self.assertGreater(recognizer.listen.call_args.kwargs["phrase_time_limit"], 0)
        stream.close.assert_called_once()
        pa.terminate.assert_called_once()
        engine.delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
