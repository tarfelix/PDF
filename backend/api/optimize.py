import asyncio
import fitz
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from services.file_manager import file_manager
from core.pdf_ops import optimize_pdf
from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE

router = APIRouter(tags=["optimize"])

PROFILES = {
    "light": {"garbage": 2, "deflate": True, "clean": True},
    "recommended": {"garbage": 3, "deflate": True, "clean": True, "deflate_images": True, "deflate_fonts": True},
    "maximum": {"garbage": 4, "deflate": True, "clean": True, "deflate_images": True, "deflate_fonts": True, "linear": True},
}


class OptimizeRequest(BaseModel):
    file_id: str
    profile: str = "recommended"  # light, recommended, maximum
    password: Optional[str] = None
    remove_annotations: bool = False
    metadata: Optional[Dict[str, str]] = None  # {title, author, subject}


def _optimize(data: bytes, req: OptimizeRequest) -> bytes:
    doc = fitz.open(stream=data, filetype="pdf")

    if req.remove_annotations:
        for page in doc:
            annots = list(page.annots()) if page.annots() else []
            for annot in annots:
                page.delete_annot(annot)

    if req.metadata:
        current = doc.metadata or {}
        current.update({k: v for k, v in req.metadata.items() if v})
        doc.set_metadata(current)

    opts = dict(PROFILES.get(req.profile, PROFILES["recommended"]))

    if req.password:
        opts.update({
            "encryption": ENCRYPT_AES_256,
            "user_pw": req.password,
            "owner_pw": req.password,
            "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE,
        })

    return optimize_pdf(doc, opts)


@router.post("/optimize")
async def optimize(req: OptimizeRequest):
    data = file_manager.get_bytes(req.file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    info = file_manager.get_info(req.file_id)
    base_name = info["filename"].rsplit(".", 1)[0] if info else "resultado"

    result = await asyncio.to_thread(_optimize, data, req)
    result_id = file_manager.store(result, f"{base_name}_otimizado.pdf")

    original_size = len(data)
    new_size = len(result)
    reduction = ((original_size - new_size) / original_size * 100) if original_size > 0 else 0

    return {
        "result_file_id": result_id,
        "filename": f"{base_name}_otimizado.pdf",
        "original_size_bytes": original_size,
        "size_bytes": new_size,
        "reduction_percent": round(reduction, 1),
    }
