"""Flask API for the Agentic RAG chatbot.

This server is intended for local development. Do not expose it publicly without
authentication, deployment hardening, and a deliberate data-retention policy.
"""

import logging
import os
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from groq import Groq
from werkzeug.utils import secure_filename

from api_validation import allowed_upload_filename, validate_question_payload
from config import GROQ_API_KEY, GROQ_MODEL
from layer3_aro import retrieve_with_analysis
from layer4_hdp import check
from layer5_analytics import is_analytics_question, answer_analytics_question
from layer6_csv_processor import csv_processor
from layer7_data_analyzer import load_dataset, is_data_question, answer_data_question


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploaded_files")))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(
    UPLOAD_FOLDER=str(UPLOAD_FOLDER),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
CORS(app, origins=allowed_origins, supports_credentials=True)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def _session_datasets():
    """Return this browser session's uploaded dataset records."""
    datasets = session.get("datasets", [])
    return datasets if isinstance(datasets, list) else []


def _selected_dataset():
    selected_id = session.get("current_dataset_id")
    return next(
        (item for item in _session_datasets() if item.get("id") == selected_id),
        None,
    )


def build_prompt(question, chunks):
    """Build a prompt using retrieved document context."""
    context = "\n\n".join(
        f"[{chunk['metadata'].get('department', 'General')}]\n{chunk['content']}"
        for chunk in chunks
    )
    return f"""You are a helpful company assistant. Answer using ONLY the context provided.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def generate_answer(question, chunks):
    """Generate an answer using the configured Groq model."""
    if client is None:
        raise RuntimeError("Groq API is not configured")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": build_prompt(question, chunks)}],
        temperature=0.3,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"status": "error", "message": "Upload exceeds the 50 MB limit."}), 413


@app.errorhandler(400)
def bad_request(_error):
    return jsonify({"status": "error", "message": "Malformed request."}), 400


@app.route("/health", methods=["GET"])
def health():
    """Return a minimal health response without exposing user dataset state."""
    return jsonify({"status": "healthy", "service": "Agentic RAG Chatbot"}), 200


@app.route("/upload", methods=["POST"])
def upload_file():
    """Validate and load a CSV or Excel dataset into the caller's session."""
    saved_path = None
    try:
        uploaded = request.files.get("file")
        if uploaded is None:
            return jsonify({"status": "error", "message": "No file provided."}), 400
        if not uploaded.filename:
            return jsonify({"status": "error", "message": "No file selected."}), 400
        if not allowed_upload_filename(uploaded.filename):
            return jsonify({
                "status": "error",
                "message": "Only CSV, XLSX, and XLS files are allowed.",
            }), 400

        original_name = secure_filename(uploaded.filename)
        if not original_name:
            return jsonify({"status": "error", "message": "Invalid filename."}), 400

        extension = Path(original_name).suffix.lower()
        dataset_id = uuid.uuid4().hex
        stored_name = f"{dataset_id}{extension}"
        saved_path = UPLOAD_FOLDER / stored_name
        uploaded.save(saved_path)

        dataframe, read_error = load_dataset(str(saved_path), dataset_id)
        if read_error or dataframe is None:
            logger.info("Rejected unreadable dataset upload (%s)", original_name)
            saved_path.unlink(missing_ok=True)
            return jsonify({
                "status": "error",
                "message": "Unable to read the upload as a valid CSV or Excel dataset.",
            }), 400

        record = {"id": dataset_id, "filename": original_name}
        datasets = [item for item in _session_datasets() if item.get("id") != dataset_id]
        datasets.append(record)
        session["datasets"] = datasets
        session["current_dataset_id"] = dataset_id

        summary = csv_processor.get_file_summary(dataframe)
        logger.info(
            "Loaded dataset %s (%s rows, %s columns)",
            original_name, summary["rows"], summary["columns"],
        )
        return jsonify({
            "status": "success",
            "message": "Dataset uploaded successfully.",
            "filename": original_name,
            "dataset_id": dataset_id,
            "summary": summary,
        }), 200
    except Exception:
        logger.exception("Dataset upload failed")
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)
        return jsonify({"status": "error", "message": "Upload failed. Check the file and try again."}), 500


@app.route("/datasets", methods=["GET"])
def list_datasets():
    """List only datasets associated with this browser session."""
    datasets = _session_datasets()
    current = session.get("current_dataset_id")
    return jsonify({
        "status": "success",
        "datasets": datasets,
        "current": current,
    }), 200


@app.route("/datasets/select", methods=["POST"])
def select_dataset():
    """Select a dataset that belongs to this browser session."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("dataset_id"), str):
        return jsonify({"status": "error", "message": "A valid dataset_id is required."}), 400
    dataset_id = payload["dataset_id"]
    if not any(item.get("id") == dataset_id for item in _session_datasets()):
        return jsonify({"status": "error", "message": "Dataset not found in this session."}), 404
    session["current_dataset_id"] = dataset_id
    return jsonify({"status": "success", "current": dataset_id}), 200


@app.route("/ask", methods=["POST"])
def ask():
    """Route a question to dataset analysis, company analytics, or document RAG."""
    try:
        payload = request.get_json(silent=True)
        question, validation_error = validate_question_payload(payload)
        if validation_error:
            return jsonify({"status": "error", "message": validation_error}), 400

        dataset = _selected_dataset()
        dataset_id = dataset.get("id") if dataset else None
        dataset_name = dataset.get("filename") if dataset else None
        logger.info("Question received (dataset selected: %s)", bool(dataset_id))

        if dataset_id and is_data_question(question):
            data_answer = answer_data_question(question, dataset_id)
            if data_answer and "Could not" not in data_answer and "I could not" not in data_answer:
                return jsonify({
                    "status": "success",
                    "question": question,
                    "answer": data_answer,
                    "confidence": None,
                    "verification_status": "not_verified",
                    "query_type": "data_analysis",
                    "sources": [{"id": dataset_name}],
                    "metadata": {"mode": "Dataset Analysis", "dataset": dataset_name},
                }), 200

        if is_analytics_question(question):
            analytics_answer = answer_analytics_question(question)
            if analytics_answer:
                return jsonify({
                    "status": "success",
                    "question": question,
                    "answer": analytics_answer,
                    "confidence": None,
                    "verification_status": "not_verified",
                    "query_type": "analytics",
                    "sources": [],
                    "metadata": {"mode": "Company Analytics"},
                }), 200

        retrieval = retrieve_with_analysis(question)
        chunks = retrieval.get("results", [])
        if not chunks:
            return jsonify({
                "status": "success",
                "question": question,
                "answer": "I cannot find a reliable answer to this question in our company documents.",
                "confidence": 0.0,
                "verification_status": "refused",
                "sources": [],
                "metadata": {"mode": "Document Search"},
            }), 200

        if client is None:
            return jsonify({
                "status": "error",
                "message": "Document answer generation is not configured. Set GROQ_API_KEY.",
            }), 503

        raw_answer = generate_answer(question, chunks)
        verification = check(raw_answer, chunks)
        status = verification.get("status", "warning")
        confidence = verification.get("confidence", 0.0)

        if status == "refused":
            final_answer = (
                "I cannot find a reliable answer to this question. "
                f"The system declined to answer. (Heuristic score: {confidence:.0%})"
            )
        elif status == "warning":
            answer_text = verification.get("answer") or "No reliable answer available."
            final_answer = f"Low-confidence answer (heuristic score: {confidence:.0%}):\n\n{answer_text}"
        else:
            final_answer = verification.get("answer") or "No answer available."

        sources = [{
            "id": chunk.get("id", "").split("_")[0],
            "department": chunk.get("metadata", {}).get("department"),
            "type": chunk.get("metadata", {}).get("document_type"),
            "score": chunk.get("score"),
        } for chunk in chunks[:3]]

        return jsonify({
            "status": "success",
            "question": question,
            "answer": final_answer,
            "confidence": confidence,
            "verification_status": status,
            "sources": sources,
            "metadata": {
                "mode": "Document Search",
                "documents_retrieved": retrieval.get("result_count", len(chunks)),
            },
        }), 200
    except Exception:
        logger.exception("Question processing failed")
        return jsonify({
            "status": "error",
            "message": "The request could not be processed. Please try again.",
        }), 500


if __name__ == "__main__":
    import subprocess
    import sys
    import threading
    import time
    import webbrowser

    def start_frontend():
        time.sleep(2)
        frontend_path = str(BASE_DIR.parent / "frontend")
        try:
            command = [sys.executable, "-m", "http.server", os.getenv("FRONTEND_PORT", "3000")]
            options = {"cwd": frontend_path}
            if sys.platform == "win32":
                options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(command, **options)
            logger.info("Frontend server started on port %s", os.getenv("FRONTEND_PORT", "3000"))
        except Exception:
            logger.exception("Could not start frontend server")

    def open_browser():
        time.sleep(4)
        webbrowser.open(os.getenv("FRONTEND_URL", "http://localhost:3000"))

    threading.Thread(target=start_frontend, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
