import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Tuple

from services.file_manager import file_manager
from core.bates import apply_bates_stamping

router = APIRouter(tags=["bates"])


class BatesRequest(BaseModel):
    file_id: str
    text_pattern: str = "Doc. {doc_idx} - Fls. {page_idx}"
    start_doc_idx: int = 1
    start_page_idx: int = 1
    position: str = "bottom_right"
    margin: int = 20
    font_size: int = 10
    color: Optional[Tuple[float, float, float]] = None


@router.post("/bates")
async def bates(req: BatesRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "resultado"
    color = req.color or (0, 0, 0)

    result = await asyncio.to_thread(
        apply_bates_stamping,
        data,
        req.text_pattern,
        req.start_doc_idx,
        req.start_page_idx,
        req.position,
        req.margin,
        req.font_size,
        color,
    )
    result_id = file_manager.store(result, f"{base_name}_bates.pdf")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_bates.pdf",
        "size_bytes": len(result),
    }
