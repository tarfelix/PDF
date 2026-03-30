import io
import asyncio
import base64
import fitz
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.file_manager import file_manager
from config import settings

router = APIRouter(tags=["thumbnails"])


def _generate_thumbnails(pdf_bytes: bytes, page_start: int, page_end: int, dpi: int) -> list[dict]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    thumbnails = []
    end = min(page_end, doc.page_count - 1)

    for i in range(page_start, end + 1):
        page = doc[i]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        thumbnails.append({
            "page": i,
            "width": pix.width,
            "height": pix.height,
            "data": f"data:image/png;base64,{b64}",
        })

    doc.close()
    return thumbnails


@router.get("/thumbnails/{file_id}")
async def get_thumbnails(
    file_id: str,
    page_start: int = Query(0, ge=0),
    page_end: int = Query(9, ge=0),
    dpi: int = Query(72, ge=36, le=150),
):
    """Generate page thumbnails for the visual editor."""
    data = file_manager.get_bytes(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    thumbnails = await asyncio.to_thread(_generate_thumbnails, data, page_start, page_end, dpi)

    return {"file_id": file_id, "thumbnails": thumbnails}
