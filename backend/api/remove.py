import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.file_manager import file_manager
from core.pdf_ops import remove_pages
from core.utils import parse_page_input

router = APIRouter(tags=["remove"])


class RemoveRequest(BaseModel):
    file_id: str
    pages: Optional[str] = None  # "1, 3-5"
    page_indices: Optional[List[int]] = None  # zero-based
    optimize: bool = True
    password: Optional[str] = None


@router.post("/remove")
async def remove(req: RemoveRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    total = doc.page_count
    doc.close()

    if req.pages:
        page_indices = parse_page_input(req.pages, total)
    elif req.page_indices:
        page_indices = req.page_indices
    else:
        raise HTTPException(status_code=400, detail="Informe pages ou page_indices")

    if not page_indices:
        raise HTTPException(status_code=400, detail="Nenhuma página válida selecionada")

    if len(page_indices) >= total:
        raise HTTPException(status_code=400, detail="Não é possível remover todas as páginas")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "resultado"

    result = await asyncio.to_thread(remove_pages, data, page_indices, req.optimize, req.password)
    result_id = file_manager.store(result, f"{base_name}_editado.pdf")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_editado.pdf",
        "pages_removed": len(page_indices),
        "pages_remaining": total - len(page_indices),
        "size_bytes": len(result),
    }
