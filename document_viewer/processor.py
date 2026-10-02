"""Format supported text documents and create browser-safe previews."""

import html
import json
import mimetypes
from pathlib import Path
from xml.etree import ElementTree

import bleach
import markdown
from bs4 import BeautifulSoup


SAFE_HTML_TAGS = bleach.sanitizer.ALLOWED_TAGS | {
    "blockquote", "br", "caption", "code", "dd", "dl", "dt", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "img", "li", "ol", "p", "pre",
    "span", "table", "tbody", "td", "th", "thead", "tr", "ul",
}
SAFE_HTML_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["alt", "src", "title"],
}
SAFE_PROTOCOLS = {"http", "https", "mailto"}
FORMAT_BY_EXTENSION = {
    ".htm": "html",
    ".html": "html",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".xml": "xml",
}
FORMAT_BY_CONTENT_TYPE = {
    "application/json": "json",
    "application/xml": "xml",
    "text/html": "html",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/xml": "xml",
}


class DocumentError(ValueError):
    """Raised when a document cannot be identified or parsed."""


def _detect_format(file_name: str, content_type: str | None) -> str:
    extension = Path(file_name).suffix.lower()
    if extension in FORMAT_BY_EXTENSION:
        return FORMAT_BY_EXTENSION[extension]

    media_type = content_type or mimetypes.guess_type(file_name)[0] or ""
    media_type = media_type.split(";", 1)[0].strip().lower()
    try:
        return FORMAT_BY_CONTENT_TYPE[media_type]
    except KeyError as error:
        raise DocumentError("Unsupported document type.") from error


def _safe_html(fragment: str) -> str:
    return bleach.clean(
        fragment,
        tags=SAFE_HTML_TAGS,
        attributes=SAFE_HTML_ATTRIBUTES,
        protocols=SAFE_PROTOCOLS,
        strip=True,
    )


def process_document(
    file_name: str, content: str, content_type: str | None = None
) -> dict[str, str | int]:
    """Return normalized source and a sanitized HTML preview for a document."""
    document_format = _detect_format(file_name, content_type)

    try:
        if document_format == "json":
            formatted_content = json.dumps(
                json.loads(content), ensure_ascii=False, indent=2
            )
            preview_html = (
                "<pre><code>" + html.escape(formatted_content) + "</code></pre>"
            )
        elif document_format == "html":
            formatted_content = BeautifulSoup(content, "html.parser").prettify()
            preview_html = _safe_html(formatted_content)
        elif document_format == "xml":
            root = ElementTree.fromstring(content)
            ElementTree.indent(root, space="  ")
            formatted_content = ElementTree.tostring(root, encoding="unicode")
            preview_html = (
                "<pre><code>" + html.escape(formatted_content) + "</code></pre>"
            )
        else:
            formatted_content = content
            rendered_markdown = markdown.markdown(
                content, extensions=["fenced_code", "tables"]
            )
            preview_html = _safe_html(rendered_markdown)
    except (json.JSONDecodeError, ElementTree.ParseError) as error:
        raise DocumentError(f"Invalid {document_format} document.") from error

    return {
        "fileName": Path(file_name).name,
        "format": document_format,
        "formattedContent": formatted_content,
        "previewHtml": preview_html,
        "characterCount": len(content),
    }