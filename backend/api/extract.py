import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.file_manager import file_manager
from core.pdf_ops import extract_pages, merge_pdfs
from core.utils import parse_page_input

router = APIRouter(tags=["extract"])


class ExtractRequest(BaseModel):
    file_id: str
    pages: Optional[str] = None  # "1, 3-5, 10"
    page_indices: Optional[List[int]] = None  # zero-based
    optimize: bool = True
    password: Optional[str] = None
    as_zip: bool = False
    segments: Optional[List[dict]] = None  # [{name, start, end}] for legal pieces


@router.post("/extract")
async def extract(req: ExtractRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "extraido"

    # Extract multiple named segments (legal pieces) → single merged PDF
    if req.segments:
        parts = []
        for seg in req.segments:
            pages = list(range(seg["start"], seg["end"] + 1))
            part_bytes = await asyncio.to_thread(
                extract_pages, data, pages, req.optimize, req.password
            )
            parts.append(part_bytes)

        merged_bytes = await asyncio.to_thread(merge_pdfs, parts, req.optimize)
        result_id = file_manager.store(merged_bytes, f"{base_name}_pecas.pdf", "application/pdf")
        return {
            "result_file_id": result_id,
            "filename": f"{base_name}_pecas.pdf",
            "segments": len(req.segments),
            "size_bytes": len(merged_bytes),
        }

    # Resolve page indices
    if req.pages:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        page_indices = parse_page_input(req.pages, doc.page_count)
        doc.close()
    elif req.page_indices:
        page_indices = req.page_indices
    else:
        raise HTTPException(status_code=400, detail="Informe pages ou page_indices")

    if not page_indices:
        raise HTTPException(status_code=400, detail="Nenhuma página válida selecionada")

    result = await asyncio.to_thread(extract_pages, data, page_indices, req.optimize, req.password)
    result_id = file_manager.store(result, f"{base_name}_extraido.pdf")

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_extraido.pdf",
        "pages_extracted": len(page_indices),
        "size_bytes": len(result),
    }
