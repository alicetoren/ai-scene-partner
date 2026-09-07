"""Convert supported uploads to text without interpreting the scene."""

from io import BytesIO
from pathlib import Path
from textwrap import dedent

import pdfplumber

from pypdf import PdfReader


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ScriptUploadError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def extract_script_text(filename: str | None, contents: bytes) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension not in {".txt", ".pdf"}:
        raise ScriptUploadError("Only TXT (.txt) and PDF (.pdf) scripts are supported.", 415)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ScriptUploadError("The script is too large. Upload a file of 10 MiB or less.", 413)
    if not contents:
        raise ScriptUploadError("The uploaded script is empty.")

    if extension == ".pdf":
        return extract_pdf_text(contents)
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ScriptUploadError("The script must be UTF-8 encoded text.") from error
    if not text.strip():
        raise ScriptUploadError("The uploaded script is empty.")
    return text


def extract_pdf_text(contents: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(contents))
        if reader.is_encrypted:
            raise ScriptUploadError("Encrypted PDFs are not supported. Upload an unencrypted PDF or a TXT script.")
        if not reader.pages:
            raise ScriptUploadError("The PDF contains no pages.")
        # Reconstruct visual coordinates rather than PDF drawing-command order.
        # pypdf layout can drop/reorder blocks in edited screenplay PDFs.
        with pdfplumber.open(BytesIO(contents)) as document:
            pages = []
            for page in document.pages:
                layout = page.extract_text(layout=True) or ""
                # Remove page margins/padding only; retain relative indentation,
                # blank lines, punctuation, and all screenplay markers for parsing.
                pages.append(dedent("\n".join(line.rstrip() for line in layout.splitlines())).strip("\n"))
            text = "\n\n".join(pages)
    except ScriptUploadError:
        raise
    except Exception as error:
        # Malformed PDFs can fail at reader creation, page traversal, or text extraction.
        raise ScriptUploadError("This PDF could not be read. Upload a valid text-based PDF or a TXT script.") from error
    if not any(character.isalnum() for character in text):
        raise ScriptUploadError(
            "No usable text could be extracted from this PDF. Image-only/scanned PDFs are not supported yet. "
            "Upload a text-based PDF or a TXT script."
        )
    return text
