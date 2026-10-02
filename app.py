"""FastAPI application for local development and AWS Lambda."""

import base64
import binascii
import json
import logging
import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from mangum import Mangum
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from lambda_function import handler


MAX_UTILITY_INPUT_CHARS = 1_048_576
BASE64URL_PATTERN = re.compile(r"[A-Za-z0-9_-]*={0,2}")
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Document Processor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("ALLOWED_ORIGIN", "*")],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["content-type"],
)


class JwtDecodeRequest(BaseModel):
    token: str = Field(min_length=1, max_length=MAX_UTILITY_INPUT_CHARS)


class Base64EncodeRequest(BaseModel):
    text: str = Field(max_length=MAX_UTILITY_INPUT_CHARS)


class Base64DecodeRequest(BaseModel):
    encoded: str = Field(max_length=MAX_UTILITY_INPUT_CHARS)


@app.exception_handler(RequestValidationError)
async def validation_error_response(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    details = []
    for item in error.errors():
        location = [str(part) for part in item["loc"]]
        if location and location[0] == "body":
            location = location[1:]
        details.append(
            {
                "field": ".".join(location) or "request",
                "message": item["msg"],
                "type": item["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed.",
            "code": "VALIDATION_ERROR",
            "details": details,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_response(
    request: Request, error: StarletteHTTPException
) -> JSONResponse:
    if isinstance(error.detail, dict) and "error" in error.detail:
        content = error.detail
    else:
        content = {"error": str(error.detail), "code": "HTTP_ERROR"}
    return JSONResponse(
        status_code=error.status_code, content=content, headers=error.headers
    )


@app.exception_handler(Exception)
async def internal_error_response(request: Request, error: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled API error")
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred.",
            "code": "INTERNAL_ERROR",
            "details": "Please retry the request or contact support.",
        },
    )


def _invoke_handler(method: str, body: bytes = b"") -> Response:
    event: dict[str, object] = {"httpMethod": method}
    if method == "POST":
        event["body"] = base64.b64encode(body).decode("ascii")
        event["isBase64Encoded"] = True

    result = handler(event, None)
    status_code = int(result["statusCode"])
    response_body = "" if status_code == 204 else str(result["body"])
    if status_code >= 400:
        error_body = json.loads(response_body)
        error_body.setdefault(
            "code",
            {
                400: "INVALID_REQUEST",
                413: "PAYLOAD_TOO_LARGE",
                415: "UNSUPPORTED_DOCUMENT_TYPE",
            }.get(status_code, "REQUEST_FAILED"),
        )
        response_body = json.dumps(error_body, ensure_ascii=False)
    headers = {str(key): str(value) for key, value in result["headers"].items()}
    return Response(content=response_body, status_code=status_code, headers=headers)


def _decode_base64url(value: str, *, allow_empty: bool = False) -> bytes:
    if not BASE64URL_PATTERN.fullmatch(value) or (not value and not allow_empty):
        raise ValueError("Invalid URL-safe Base64 characters.")

    unpadded = value.rstrip("=")
    supplied_padding = len(value) - len(unpadded)
    required_padding = (-len(unpadded)) % 4
    if len(unpadded) % 4 == 1 or supplied_padding not in (0, required_padding):
        raise ValueError("Invalid URL-safe Base64 padding.")

    padded = unpadded + ("=" * required_padding)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


def _decode_jwt_json_segment(segment: str, name: str) -> dict[str, Any]:
    try:
        decoded = _decode_base64url(segment)
        value = json.loads(decoded)
    except (ValueError, binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"JWT {name} must be URL-safe Base64-encoded JSON.",
                "code": "INVALID_JWT",
            },
        ) from error

    if not isinstance(value, dict):
        raise HTTPException(
            status_code=400,
            detail={"error": f"JWT {name} must be a JSON object.", "code": "INVALID_JWT"},
        )
    return value


@app.post("/documents/process")
async def process_document(request: Request) -> Response:
    return _invoke_handler("POST", await request.body())


@app.options("/documents/process")
@app.options("/utilities/jwt/decode")
@app.options("/utilities/base64/url/encode")
@app.options("/utilities/base64/url/decode")
async def preflight() -> Response:
    return _invoke_handler("OPTIONS")


@app.post("/utilities/jwt/decode")
async def decode_jwt(request: JwtDecodeRequest) -> dict[str, Any]:
    segments = request.token.split(".")
    if len(segments) != 3:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "A JWT must contain exactly three dot-separated segments.",
                "code": "INVALID_JWT",
            },
        )

    try:
        _decode_base64url(segments[2], allow_empty=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "JWT signature must use URL-safe Base64 characters.",
                "code": "INVALID_JWT",
            },
        ) from error

    return {
        "header": _decode_jwt_json_segment(segments[0], "header"),
        "payload": _decode_jwt_json_segment(segments[1], "payload"),
        "signature": segments[2],
        "verified": False,
    }


@app.post("/utilities/base64/url/encode")
async def encode_base64url(request: Base64EncodeRequest) -> dict[str, str]:
    encoded = base64.urlsafe_b64encode(request.text.encode("utf-8"))
    return {"encoded": encoded.decode("ascii").rstrip("=")}


@app.post("/utilities/base64/url/decode")
async def decode_base64url(request: Base64DecodeRequest) -> dict[str, str]:
    try:
        decoded = _decode_base64url(request.encoded, allow_empty=True).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Input must be valid URL-safe Base64 containing UTF-8 text.",
                "code": "INVALID_BASE64",
            },
        ) from error
    return {"decoded": decoded}


lambda_handler = Mangum(app)