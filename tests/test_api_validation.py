"""Unit tests for API input validation; these require only the Python standard library."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "chatbot-rag", "backend"))

from api_validation import allowed_upload_filename, validate_question_payload


class UploadFilenameTests(unittest.TestCase):
    def test_accepts_supported_extensions_case_insensitively(self):
        for name in ("data.csv", "report.XLSX", "legacy.XLS"):
            with self.subTest(name=name):
                self.assertTrue(allowed_upload_filename(name))

    def test_rejects_unsupported_or_empty_names(self):
        for name in ("", "../data.csv.exe", "data.csv.exe", "data.txt", None):
            with self.subTest(name=name):
                self.assertFalse(allowed_upload_filename(name))


class QuestionPayloadTests(unittest.TestCase):
    def test_trims_valid_question(self):
        self.assertEqual(validate_question_payload({"question": "  Hello?  "}), ("Hello?", None))

    def test_rejects_non_object_payload(self):
        self.assertEqual(validate_question_payload(None), (None, "Request body must be a JSON object."))

    def test_rejects_missing_or_non_string_question(self):
        self.assertEqual(validate_question_payload({}), (None, "Field 'question' must be a string."))
        self.assertEqual(validate_question_payload({"question": 7}), (None, "Field 'question' must be a string."))

    def test_rejects_empty_and_oversized_question(self):
        self.assertIsNotNone(validate_question_payload({"question": "   "})[1])
        self.assertIsNotNone(validate_question_payload({"question": "x" * 4001})[1])


if __name__ == "__main__":
    unittest.main()
