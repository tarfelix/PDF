import io
import zipfile
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.file_manager import file_manager
from core.pdf_ops import split_pdf_by_count, split_pdf_by_size, split_pdf_by_bookmarks

router = APIRouter(tags=["split"])


class SplitRequest(BaseModel):
    file_id: str
    mode: str  # "count", "size", "bookmark"
    value: float  # pages per part, max MB, or bookmark level
    optimize: bool = True


@router.post("/split")
async def split(req: SplitRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "split"

    if req.mode == "count":
        parts = await asyncio.to_thread(split_pdf_by_count, data, int(req.value), req.optimize)
    elif req.mode == "size":
        parts = await asyncio.to_thread(split_pdf_by_size, data, req.value, req.optimize)
    elif req.mode == "bookmark":
        parts = await asyncio.to_thread(split_pdf_by_bookmarks, data, int(req.value), req.optimize)
    else:
        raise HTTPException(status_code=400, detail=f"Modo inválido: {req.mode}")

    if len(parts) == 1:
        suffix, part_bytes = parts[0]
        result_id = file_manager.store(part_bytes, f"{base_name}{suffix}.pdf")
        return {
            "result_file_id": result_id,
            "filename": f"{base_name}{suffix}.pdf",
            "parts": 1,
            "size_bytes": len(part_bytes),
        }

    # Multiple parts → ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for suffix, part_bytes in parts:
            zf.writestr(f"{base_name}{suffix}.pdf", part_bytes)

    zip_bytes = zip_buffer.getvalue()
    result_id = file_manager.store(zip_bytes, f"{base_name}_partes.zip", "application/zip")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_partes.zip",
        "parts": len(parts),
        "size_bytes": len(zip_bytes),
    }
