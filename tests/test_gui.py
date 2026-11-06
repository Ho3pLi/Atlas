"""Headless Qt smoke test of multi-turn meal preferences and literal chat text."""

import json
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from atlas import config, gui


class GuiTests(unittest.TestCase):
    def test_meal_preferences_do_not_block_on_stdin(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}):
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QTextEdit

            original_exec = QApplication.exec
            errors, transcripts = [], []
            answers = iter(
                [
                    "piano pasti",
                    "<b>nessuna</b>",
                    "leggeri",
                    "pesce",
                    "riso",
                    "2",
                    "si",
                    "cambia pasto",
                ]
            )

            def run_loop(application):
                deadline = time.monotonic() + 10

                def tick():
                    try:
                        if time.monotonic() > deadline:
                            raise AssertionError("GUI input remained blocked")
                        window = next(
                            widget
                            for widget in application.topLevelWidgets()
                            if widget.findChild(QTextEdit) is not None
                        )
                        button = window.findChild(QPushButton)
                        if button.isEnabled():
                            answer = next(answers, None)
                            if answer is None:
                                transcripts.append(
                                    window.findChild(QTextEdit).toPlainText()
                                )
                                window.close()
                                application.quit()
                                return
                            window.findChild(QLineEdit).setText(answer)
                            button.click()
                        QTimer.singleShot(20, tick)
                    except BaseException as exc:
                        errors.append(exc)
                        application.quit()

                QTimer.singleShot(0, tick)
                return original_exec()

            plan = {"pranzo": "riso", "cena": "zuppa"}
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=json.dumps(plan)))
                ]
            )
            with (
                patch.object(config, "session", config.SessionState()),
                patch.object(config, "get_groq_client") as client,
                patch.object(QApplication, "exec", run_loop),
                patch("builtins.input", side_effect=AssertionError("GUI read stdin")),
            ):
                client.return_value.chat.completions.create.return_value = response
                gui.run()
                self.assertEqual(errors, [])
                self.assertEqual(
                    client.return_value.chat.completions.create.call_count, 2
                )
                self.assertEqual(config.session.meal_plan["Lunedi"], plan)
            self.assertIn("<b>nessuna</b>", transcripts[0])
            self.assertEqual(transcripts[0].count("cena: zuppa"), 2)


if __name__ == "__main__":
    unittest.main()
