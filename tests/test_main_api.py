"""Focused Flask route tests with downstream RAG services stubbed out."""

import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "chatbot-rag", "backend"))

# The route tests do not need live Groq, ChromaDB, embeddings, or analytics files.
def _module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _Groq:
    def __init__(self, **_kwargs):
        pass


_module("groq", Groq=_Groq)
_module("config", GROQ_API_KEY=None, GROQ_MODEL="test-model")
_module("layer3_aro", retrieve_with_analysis=lambda _question: {"results": [], "result_count": 0})
_module("layer4_hdp", check=lambda _answer, _chunks: {})
_module("layer5_analytics", is_analytics_question=lambda _question: False, answer_analytics_question=lambda _question: None)


class _CSVProcessor:
    def get_file_summary(self, dataframe):
        return {"rows": len(dataframe), "columns": len(dataframe.columns), "column_names": list(dataframe.columns)}


_module("layer6_csv_processor", csv_processor=_CSVProcessor())
_module(
    "layer7_data_analyzer",
    load_dataset=lambda _filepath, _filename: (None, "not used in these tests"),
    is_data_question=lambda _question: False,
    answer_data_question=lambda _question, _filename: None,
)

import main as api


class ApiRouteTests(unittest.TestCase):
    def setUp(self):
        api.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = api.app.test_client()

    def test_malformed_json_returns_400(self):
        response = self.client.post("/ask", data="not-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "error")

    def test_missing_question_returns_400(self):
        response = self.client.post("/ask", json={})
        self.assertEqual(response.status_code, 400)

    def test_unsupported_upload_extension_returns_400(self):
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"not a dataset"), "notes.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    def test_dataset_listing_is_session_scoped(self):
        first_client = api.app.test_client()
        second_client = api.app.test_client()
        with first_client.session_transaction() as session:
            session["datasets"] = [{"id": "session-one-id", "filename": "private.csv"}]
            session["current_dataset_id"] = "session-one-id"

        first_response = first_client.get("/datasets")
        second_response = second_client.get("/datasets")
        self.assertEqual(first_response.get_json()["datasets"][0]["filename"], "private.csv")
        self.assertEqual(second_response.get_json()["datasets"], [])

    def test_session_cannot_select_another_sessions_dataset(self):
        first_client = api.app.test_client()
        second_client = api.app.test_client()
        with first_client.session_transaction() as session:
            session["datasets"] = [{"id": "session-one-id", "filename": "private.csv"}]

        response = second_client.post("/datasets/select", json={"dataset_id": "session-one-id"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
