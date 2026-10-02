"""API Gateway Lambda entry point for document formatting requests."""

import base64
import binascii
import json
import os

from document_viewer.processor import DocumentError, process_document


MAX_DOCUMENT_BYTES = 1_048_576


def _response(status_code: int, body: dict[str, object]) -> dict[str, object]:
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
            "Content-Type": "application/json; charset=utf-8",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    """Handle an API Gateway proxy event."""
    if event.get("httpMethod") == "OPTIONS":
        return _response(204, {})

    raw_body = event.get("body")
    if not isinstance(raw_body, str):
        return _response(400, {"error": "Request body must be JSON."})

    try:
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body, validate=True).decode("utf-8")
        if len(raw_body.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            return _response(413, {"error": "Request body exceeds the 1 MiB limit."})
        request = json.loads(raw_body)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return _response(400, {"error": "Request body must be valid UTF-8 JSON."})

    if not isinstance(request, dict):
        return _response(400, {"error": "Request body must be a JSON object."})

    file_name = request.get("fileName")
    content = request.get("content")
    content_type = request.get("contentType")
    if not isinstance(file_name, str) or not file_name.strip():
        return _response(400, {"error": "fileName is required."})
    if not isinstance(content, str):
        return _response(400, {"error": "content must be a string."})
    if content_type is not None and not isinstance(content_type, str):
        return _response(400, {"error": "contentType must be a string."})

    try:
        result = process_document(file_name, content, content_type)
    except DocumentError as error:
        status_code = 415 if str(error) == "Unsupported document type." else 400
        return _response(status_code, {"error": str(error)})

    return _response(200, result)