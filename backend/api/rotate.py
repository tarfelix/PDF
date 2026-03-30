import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict

from services.file_manager import file_manager
from core.pdf_ops import rotate_pages

router = APIRouter(tags=["rotate"])


class RotateRequest(BaseModel):
    file_id: str
    rotations: Dict[int, int]  # {page_index: angle}
    optimize: bool = True


@router.post("/rotate")
async def rotate(req: RotateRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    if not req.rotations:
        raise HTTPException(status_code=400, detail="Nenhuma rotação especificada")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "resultado"

    # Convert string keys to int (JSON sends string keys)
    rotations = {int(k): v for k, v in req.rotations.items()}

    result = await asyncio.to_thread(rotate_pages, data, rotations, req.optimize)
    result_id = file_manager.store(result, f"{base_name}_rotacionado.pdf")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_rotacionado.pdf",
        "size_bytes": len(result),
    }
