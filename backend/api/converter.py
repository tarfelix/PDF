import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from services.file_manager import file_manager
from core.pdf_ops import images_to_pdf

router = APIRouter(tags=["converter"])


class ConverterRequest(BaseModel):
    file_ids: List[str]
    optimize: bool = True


@router.post("/images-to-pdf")
async def convert_images(req: ConverterRequest):
    if not req.file_ids:
        raise HTTPException(status_code=400, detail="Nenhuma imagem fornecida")

    image_list = []
    for fid in req.file_ids:
        data = file_manager.get_bytes(fid)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Arquivo {fid} não encontrado")
        image_list.append(data)

    result = await asyncio.to_thread(images_to_pdf, image_list, req.optimize)
    result_id = file_manager.store(result, "imagens_convertidas.pdf")

    return {
        "result_file_id": result_id,
        "filename": "imagens_convertidas.pdf",
        "size_bytes": len(result),
    }
