"""Validate local PDF resources; no knowledge-point extraction is performed."""
import re
from pathlib import Path
from pypdf import PdfReader


def read_pdf_page_count(static_folder, file_url):
    prefix = "/static/pdfs/"
    if not isinstance(file_url, str) or not file_url.startswith(prefix):
        raise ValueError("PDF must be stored in static/pdfs.")
    filename = file_url[len(prefix):]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.pdf", filename):
        raise ValueError("Invalid PDF filename.")
    root = (Path(static_folder) / "pdfs").resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("The PDF file does not exist in static/pdfs.")
    try:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("The file is not a valid PDF.")
            stream.seek(0)
            reader = PdfReader(stream)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported by this prototype.")
            pages = len(reader.pages)
            if pages < 1:
                raise ValueError("The PDF must contain at least one page.")
            return pages
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Cannot read the PDF. Check that the file is complete and valid.") from exc


def validate_registered_pdf(static_folder, file_url, total_pages):
    actual = read_pdf_page_count(static_folder, file_url)
    if actual != total_pages:
        raise ValueError(f"This PDF has {actual} pages; enter its actual page count.")
    return actual
