import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from services.file_manager import file_manager
from core.diff import compare_pdfs

router = APIRouter(tags=["diff"])


class DiffRequest(BaseModel):
    file_id_a: str
    file_id_b: str


@router.post("/diff")
async def diff(req: DiffRequest):
    data_a = file_manager.get_bytes(req.file_id_a)
    data_b = file_manager.get_bytes(req.file_id_b)

    if data_a is None or data_b is None:
        raise HTTPException(status_code=404, detail="Um ou ambos os arquivos não foram encontrados")

    html = await asyncio.to_thread(compare_pdfs, data_a, data_b)

    return HTMLResponse(content=html)
