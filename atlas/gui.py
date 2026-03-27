import logging
import threading

import atlas


def run():
    try:
        from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
        from PyQt6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("PyQt6 non installato. Esegui: pip install PyQt6") from exc

    class UiSignals(QObject):
        append_message = pyqtSignal(str)
        unlock_input = pyqtSignal()

    class AtlasWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.signals = UiSignals()
            self.signals.append_message.connect(self._append_message)
            self.signals.unlock_input.connect(self._unlock_input)
            self._setup_ui()

        def _setup_ui(self):
            self.setWindowTitle("Atlas - GUI")
            self.resize(900, 620)

            root = QWidget(self)
            self.setCentralWidget(root)

            layout = QVBoxLayout(root)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            title = QLabel("Atlas")
            title.setStyleSheet("font-size: 24px; font-weight: 600;")
            subtitle = QLabel("Assistente multimodale - modalità chat")
            subtitle.setStyleSheet("font-size: 13px; color: #666;")

            self.chat_box = QTextEdit()
            self.chat_box.setReadOnly(True)
            self.chat_box.setPlaceholderText("Qui compariranno i messaggi...")

            input_row = QHBoxLayout()
            self.prompt_input = QLineEdit()
            self.prompt_input.setPlaceholderText("Scrivi qui, per esempio: apri chrome")
            self.send_button = QPushButton("Invia")

            input_row.addWidget(self.prompt_input)
            input_row.addWidget(self.send_button)

            layout.addWidget(title)
            layout.addWidget(subtitle)
            layout.addWidget(self.chat_box)
            layout.addLayout(input_row)

            self.send_button.clicked.connect(self._handle_send)
            self.prompt_input.returnPressed.connect(self._handle_send)

            self._append_message("Atlas: GUI inizializzata. Scrivi un messaggio per iniziare.")

        def _append_message(self, message):
            self.chat_box.append(message)

        def _set_input_enabled(self, enabled):
            self.prompt_input.setEnabled(enabled)
            self.send_button.setEnabled(enabled)
            if enabled:
                self.prompt_input.setFocus(Qt.FocusReason.OtherFocusReason)

        def _lock_input(self):
            self._set_input_enabled(False)

        @pyqtSlot()
        def _unlock_input(self):
            self._set_input_enabled(True)

        def _handle_send(self):
            prompt = self.prompt_input.text().strip()
            if not prompt:
                return

            self.prompt_input.clear()
            self._append_message(f"Tu: {prompt}")
            self._append_message("Atlas: sto elaborando...")
            self._lock_input()

            worker = threading.Thread(target=self._process_prompt_worker, args=(prompt,), daemon=True)
            worker.start()

        def _process_prompt_worker(self, prompt):
            try:
                response = atlas.process_user_prompt(prompt)
            except Exception as exc:
                logging.exception("GUI prompt processing failed: %s", exc)
                response = "Si e verificato un errore durante l'elaborazione della richiesta."

            if not response:
                response = "Nessuna risposta disponibile."

            self.signals.append_message.emit(f"Atlas: {response}")
            self.signals.unlock_input.emit()

    app = QApplication([])
    window = AtlasWindow()
    window.show()
    app.exec()
