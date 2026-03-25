import unittest
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
        self.assertIn("problem while searching", outcome["message"])


if __name__ == "__main__":
    unittest.main()
