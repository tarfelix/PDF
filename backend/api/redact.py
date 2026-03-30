import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.file_manager import file_manager
from core.redact import redact_text_matches

router = APIRouter(tags=["redact"])


class RedactRequest(BaseModel):
    file_id: str
    keywords: List[str] = []
    ignore_case: bool = True
    patterns: List[str] = []  # ["cpf", "cnpj", "email", "date"]


@router.post("/redact")
async def redact(req: RedactRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    if not req.keywords and not req.patterns:
        raise HTTPException(status_code=400, detail="Informe keywords e/ou patterns")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "resultado"

    result, count = await asyncio.to_thread(
        redact_text_matches,
        data,
        req.keywords,
        req.ignore_case,
        req.patterns if req.patterns else None,
    )
    result_id = file_manager.store(result, f"{base_name}_tarjado.pdf")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_tarjado.pdf",
        "redactions_applied": count,
        "size_bytes": len(result),
    }
