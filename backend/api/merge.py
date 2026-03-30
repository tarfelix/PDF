import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.file_manager import file_manager
from core.pdf_ops import merge_pdfs

router = APIRouter(tags=["merge"])


class MergeRequest(BaseModel):
    file_ids: List[str]
    optimize: bool = True
    password: Optional[str] = None


@router.post("/merge")
async def merge(req: MergeRequest):
    if len(req.file_ids) < 2:
        raise HTTPException(status_code=400, detail="Pelo menos 2 arquivos são necessários")

    pdf_list = []
    for fid in req.file_ids:
        data = file_manager.get_bytes(fid)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Arquivo {fid} não encontrado")
        pdf_list.append(data)

    result = await asyncio.to_thread(merge_pdfs, pdf_list, req.optimize, req.password)
    result_id = file_manager.store(result, "mesclado.pdf")

    return {
        "result_file_id": result_id,
        "filename": "mesclado.pdf",
        "size_bytes": len(result),
    }
