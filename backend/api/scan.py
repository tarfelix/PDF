import asyncio
import fitz
from fastapi import APIRouter, HTTPException

from services.file_manager import file_manager
from core.pdf_scanner import smart_scan, get_bookmark_ranges

router = APIRouter(tags=["scan"])


@router.post("/scan")
async def scan(file_id: str):
    """Smart scan for legal document pieces."""
    data = file_manager.get_bytes(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    def _scan(pdf_bytes: bytes):
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pieces = smart_scan(doc)
        bookmarks = get_bookmark_ranges(doc)
        page_count = doc.page_count
        doc.close()
        return pieces, bookmarks, page_count

    pieces, bookmarks, page_count = await asyncio.to_thread(_scan, data)

    return {
        "file_id": file_id,
        "page_count": page_count,
        "pieces": pieces,
        "bookmarks": bookmarks,
    }
