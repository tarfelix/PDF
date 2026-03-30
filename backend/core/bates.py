import fitz
from typing import Tuple


def apply_bates_stamping(
    pdf_bytes: bytes,
    text_pattern: str = "Doc. {doc_idx} - Fls. {page_idx}",
    start_doc_idx: int = 1,
    start_page_idx: int = 1,
    position: str = "bottom_right",
    margin: int = 20,
    font_size: int = 10,
    color: Tuple[float, float, float] = (0, 0, 0),
) -> bytes:
    """Aplica carimbo (Bates Numbering) nas páginas."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for i, page in enumerate(doc):
        rect = page.rect
        w, h = rect.width, rect.height

        current_text = text_pattern.format(
            doc_idx=start_doc_idx, page_idx=start_page_idx + i
        )

        h_text = font_size * 2

        if "top" in position:
            y0 = margin
            y1 = margin + h_text
        else:
            y0 = h - margin - h_text
            y1 = h - margin

        if "left" in position:
            align = 0
        elif "center" in position:
            align = 1
        else:
            align = 2

        x0 = margin
        x1 = w - margin

        rect_insert = fitz.Rect(x0, y0, x1, y1)
        page.insert_textbox(
            rect_insert,
            current_text,
            fontsize=font_size,
            fontname="helv",
            color=color,
            align=align,
        )

    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out
