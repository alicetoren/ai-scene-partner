"""Convert supported uploads to text without interpreting the scene."""

from io import BytesIO
from pathlib import Path

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
        # Group positioned glyphs/words into visual lines. Plain extraction can put
        # every text object on a new line, even when a PDF looks normal on screen.
        # Keep vertical whitespace, indentation, and page boundaries; do not guess
        # which spaces or wrapped lines should be deleted or merged.
        text = "\n\n".join(
            (page.extract_text(extraction_mode="layout", layout_mode_strip_rotated=False) or "")
            if "/Contents" in page else ""  # Truly blank pages have no content stream.
            for page in reader.pages
        )
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
