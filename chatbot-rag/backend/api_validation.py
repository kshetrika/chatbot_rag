"""Small, dependency-free validation helpers for the Flask API."""

MAX_QUESTION_LENGTH = 4000
ALLOWED_UPLOAD_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls"})


def allowed_upload_filename(filename):
    """Return whether a filename has an accepted tabular-data extension."""
    if not isinstance(filename, str) or not filename.strip():
        return False
    return "." in filename and ("." + filename.rsplit(".", 1)[-1].lower()) in ALLOWED_UPLOAD_EXTENSIONS


def validate_question_payload(payload):
    """Return (question, error_message); malformed payloads never raise."""
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."
    question = payload.get("question")
    if not isinstance(question, str):
        return None, "Field 'question' must be a string."
    question = question.strip()
    if not question:
        return None, "Question must not be empty."
    if len(question) > MAX_QUESTION_LENGTH:
        return None, f"Question must be at most {MAX_QUESTION_LENGTH} characters."
    return question, None
