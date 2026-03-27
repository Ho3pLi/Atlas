import unittest
from unittest.mock import patch

import atlas.config as config
from atlas import appLauncher


class AppLauncherTests(unittest.TestCase):
    def setUp(self):
        self.original_aliases = dict(config.app.app_aliases)
        config.app.app_aliases = {
            "chrome": "chrome.exe",
            "blocco note": "notepad.exe",
            "discord": "discord.exe",
            "medal": "medal.exe",
            "valorant": "RiotClientServices.exe --launch-product=valorant --launch-patchline=live",
        }

    def tearDown(self):
        config.app.app_aliases = self.original_aliases

    def test_extract_app_name(self):
        app_name = appLauncher.extractAppName("Apri programma Chrome per favore")
        self.assertEqual(app_name, "chrome")

    def test_extract_app_name_for_close_action(self):
        app_name = appLauncher.extractAppName("chiudi discord", patterns=appLauncher.APP_CLOSE_PATTERNS)
        self.assertEqual(app_name, "discord")

    def test_resolve_app_alias(self):
        target = appLauncher.resolveAppAlias("Blocco Note")
        self.assertEqual(target, "notepad.exe")

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    @patch("atlas.appLauncher.subprocess.Popen")
    def test_handle_app_launch_prompt_success(self, popen_mock, _resolve_mock):
        result = appLauncher.handleAppLaunchPrompt("avvia chrome")

        self.assertEqual(result["status"], "ok")
        self.assertIn("Apro chrome", result["message"])
        popen_mock.assert_called_once()
        called_args, called_kwargs = popen_mock.call_args
        self.assertEqual(called_args[0], [r"C:\Program Files\Google\Chrome\Application\chrome.exe"])
        self.assertIsNotNone(called_kwargs["stdin"])
        self.assertIsNotNone(called_kwargs["stdout"])
        self.assertIsNotNone(called_kwargs["stderr"])

    def test_handle_app_launch_prompt_not_found(self):
        result = appLauncher.handleAppLaunchPrompt("apri programma zoom")

        self.assertEqual(result["status"], "not_found")
        self.assertIn("alias configurato", result["message"])

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Riot Games\Riot Client\RiotClientServices.exe")
    @patch("atlas.appLauncher.subprocess.Popen")
    def test_handle_app_launch_prompt_with_command_args(self, popen_mock, _resolve_mock):
        result = appLauncher.handleAppLaunchPrompt("avvia valorant")

        self.assertEqual(result["status"], "ok")
        popen_mock.assert_called_once()
        called_args, _ = popen_mock.call_args
        self.assertEqual(
            called_args[0],
            [r"C:\Riot Games\Riot Client\RiotClientServices.exe", "--launch-product=valorant", "--launch-patchline=live"],
        )

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Users\test\AppData\Local\Discord\Update.exe")
    @patch("atlas.appLauncher.subprocess.Popen")
    def test_handle_discord_update_fallback_adds_process_args(self, popen_mock, _resolve_mock):
        result = appLauncher.handleAppLaunchPrompt("apri discord")

        self.assertEqual(result["status"], "ok")
        popen_mock.assert_called_once()
        called_args, _ = popen_mock.call_args
        self.assertEqual(
            called_args[0],
            [r"C:\Users\test\AppData\Local\Discord\Update.exe", "--processStart", "Discord.exe"],
        )

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Users\test\AppData\Local\Medal\Update.exe")
    @patch("atlas.appLauncher.subprocess.Popen")
    def test_handle_medal_update_fallback_adds_process_args(self, popen_mock, _resolve_mock):
        result = appLauncher.handleAppLaunchPrompt("apri medal")

        self.assertEqual(result["status"], "ok")
        popen_mock.assert_called_once()
        called_args, _ = popen_mock.call_args
        self.assertEqual(
            called_args[0],
            [r"C:\Users\test\AppData\Local\Medal\Update.exe", "--processStart", "Medal.exe"],
        )

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    @patch("atlas.appLauncher.subprocess.run")
    def test_handle_close_app_prompt_success(self, run_mock, _resolve_mock):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stderr = ""
        result = appLauncher.handleCloseAppPrompt("chiudi chrome")

        self.assertEqual(result["status"], "ok")
        run_mock.assert_called_once_with(
            ["taskkill", "/IM", "chrome.exe", "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("atlas.appLauncher._resolve_executable", return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    @patch("atlas.appLauncher.subprocess.run")
    def test_handle_close_app_prompt_failure(self, run_mock, _resolve_mock):
        run_mock.return_value.returncode = 1
        run_mock.return_value.stderr = "not running"
        result = appLauncher.handleCloseAppPrompt("chiudi chrome")

        self.assertEqual(result["status"], "error")
        self.assertIn("Verifica che sia in esecuzione", result["message"])


if __name__ == "__main__":
    unittest.main()
