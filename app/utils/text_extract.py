"""Text extraction helpers for courseware files."""
import io


def extract_pdf_text(data, max_chars=60000):
    """Extract text from a PDF given raw bytes.

    Args:
        data: PDF file contents as bytes.
        max_chars: Upper bound on returned text length to control API cost.

    Returns:
        Extracted text prefixed with the page number of each page.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    total = 0
    for index, page in enumerate(reader.pages, start=1):
        if total >= max_chars:
            break
        text = page.extract_text() or ""
        chunk = f"[Page {index}]\n{text}\n"
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts)[:max_chars]


def extract_pptx_text(data, max_chars=60000):
    """Extract text from a PPTX given raw bytes.

    Args:
        data: PPTX file contents as bytes.
        max_chars: Upper bound on returned text length.

    Returns:
        Extracted text prefixed with the slide number.
    """
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    parts = []
    total = 0
    for index, slide in enumerate(prs.slides, start=1):
        if total >= max_chars:
            break
        lines = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                lines.append(shape.text.strip())
        chunk = f"[Slide {index}]\n" + "\n".join(lines) + "\n"
        parts.append(chunk)
        total += len(chunk)
    return "".join(parts)[:max_chars]
