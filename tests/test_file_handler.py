import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from atlas import fileHandler


class FileHandlerTests(unittest.TestCase):
    def test_build_file_search_response_multiple(self):
        matches = [
            r"C:\Docs\thesis.pdf",
            r"C:\Docs\notes.docx",
        ]

        result = fileHandler.buildFileSearchResponse(matches)

        self.assertEqual(result["status"], "multiple")
        self.assertEqual(result["matches"], matches)
        self.assertIn("1. thesis.pdf", result["message"])
        self.assertIn("2. notes.docx", result["message"])

    def test_resolve_file_choice_by_index(self):
        file_list = [
            r"C:\Docs\thesis.pdf",
            r"C:\Docs\notes.docx",
        ]

        chosen = fileHandler.resolveFileChoice("apri il file numero 2", file_list)

        self.assertEqual(chosen, r"C:\Docs\notes.docx")

    def test_handle_file_search_prompt_returns_error_outcome_on_failure(self):
        with patch("atlas.fileHandler.searchFiles", side_effect=RuntimeError("failure")):
            outcome = fileHandler.handleFileSearchPrompt("trova il file tesi")

        self.assertEqual(outcome["status"], "error")
        self.assertIn("problema durante la ricerca", outcome["message"])


class FileSummaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.model = self.enterContext(patch("atlas.fileHandler.atlas.groqPrompt"))
        self.model.return_value = "Riassunto sintetico."

    def assert_no_summary(self, path, expected):
        self.assertEqual(fileHandler.summarizeFile(str(path)), expected)
        self.model.assert_not_called()

    def test_missing_file_returns_error_without_calling_model(self):
        self.assert_no_summary(self.root / "missing.txt", "Errore: file non trovato.")

    def test_unreadable_text_returns_error_without_calling_model(self):
        path = self.root / "notes.txt"
        path.write_text("contenuto", encoding="utf-8")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            self.assert_no_summary(path, "Errore: impossibile leggere il file.")

    def test_empty_and_whitespace_text_do_not_call_model(self):
        path = self.root / "empty.txt"
        for content in ("", " \n\t "):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assert_no_summary(path, "Nessun contenuto leggibile.")
                self.assertEqual(fileHandler.readFileContent(str(path)), content)

    def test_unsupported_file_does_not_call_model(self):
        path = self.root / "photo.png"
        path.write_bytes(b"unsupported")
        self.assert_no_summary(path, "Nessun contenuto leggibile.")

    def test_unreadable_pdf_and_docx_do_not_call_model(self):
        for extension, reader, error in (
            (".pdf", "pdfplumber.open", "Errore: impossibile leggere il PDF."),
            (".docx", "docx.Document", "Errore: impossibile leggere il documento."),
        ):
            with self.subTest(extension=extension):
                path = self.root / ("unreadable" + extension)
                path.write_bytes(b"synthetic")
                with patch(reader, side_effect=PermissionError("denied")):
                    self.assert_no_summary(path, error)

    def test_malformed_pdf_and_docx_do_not_call_model(self):
        for extension, error in (
            (".pdf", "Errore: impossibile leggere il PDF."),
            (".docx", "Errore: impossibile leggere il documento."),
        ):
            with self.subTest(extension=extension):
                path = self.root / ("broken" + extension)
                path.write_bytes(b"invalid document")
                self.assert_no_summary(path, error)

    def test_pdf_without_readable_text_does_not_call_model(self):
        path = self.root / "blank.pdf"
        path.touch()
        for text in (None, "", " \n "):
            with self.subTest(text=text), patch("pdfplumber.open") as reader:
                reader.return_value.__enter__.return_value.pages = [
                    SimpleNamespace(extract_text=lambda: text)
                ]
                self.assert_no_summary(path, "Nessun testo leggibile trovato nel PDF.")

    def test_docx_without_readable_text_does_not_call_model(self):
        from docx import Document

        path = self.root / "blank.docx"
        document = Document()
        document.add_paragraph(" \t ")
        document.save(path)
        self.assert_no_summary(path, "Nessun testo leggibile trovato nel documento.")

    def test_valid_text_including_status_like_prefixes_is_summarized(self):
        path = self.root / "notes.txt"
        for text in ("Contenuto normale.", "Error: valid file contents.",
                     "Errore: un esempio nel documento.", "Nessun contenuto leggibile."):
            with self.subTest(text=text):
                self.model.reset_mock()
                path.write_text(text, encoding="utf-8")
                self.assertEqual(fileHandler.summarizeFile(str(path)), "Riassunto sintetico.")
                self.model.assert_called_once_with(
                    "Riassumi il seguente contenuto del file in 2-3 frasi in italiano: " + text,
                    None, None, None,
                )

    def test_docx_content_is_summarized(self):
        from docx import Document

        path = self.root / "notes.docx"
        document = Document()
        document.add_paragraph("Prima riga.")
        document.add_paragraph("Seconda riga.")
        document.save(path)
        self.assertEqual(fileHandler.summarizeFile(str(path)), "Riassunto sintetico.")
        self.assertIn("Prima riga.\nSeconda riga.", self.model.call_args.args[0])

    def test_summary_keeps_input_limit(self):
        path = self.root / "long.txt"
        path.write_text("x" * 2500, encoding="utf-8")
        fileHandler.summarizeFile(str(path))
        self.assertEqual(self.model.call_args.args[0].split(": ", 1)[1], "x" * 2000)

    def test_model_failure_returns_existing_fallback(self):
        path = self.root / "notes.txt"
        path.write_text("Contenuto valido.", encoding="utf-8")
        self.model.side_effect = RuntimeError("model unavailable")
        self.assertEqual(fileHandler.summarizeFile(str(path)),
                         "Ho trovato il file, ma non sono riuscito a riassumerne il contenuto.")


if __name__ == "__main__":
    unittest.main()
