import fitz
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from typing import List

from services.file_manager import file_manager

router = APIRouter(tags=["files"])


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload one or more files. Returns file_id and metadata for each."""
    results = []
    for f in files:
        data = await f.read()
        content_type = f.content_type or "application/octet-stream"
        file_id = file_manager.store(data, f.filename or "upload", content_type)

        meta = {"file_id": file_id, "filename": f.filename, "size_bytes": len(data)}

        if content_type == "application/pdf" or (f.filename and f.filename.lower().endswith(".pdf")):
            try:
                doc = fitz.open(stream=data, filetype="pdf")
                toc = doc.get_toc(simple=False)
                bookmarks = []
                for i, item in enumerate(toc):
                    lvl, title, page1 = item[0], item[1], item[2]
                    bookmarks.append({
                        "level": lvl,
                        "title": title,
                        "page": page1,
                    })
                meta["pages"] = doc.page_count
                meta["bookmarks"] = bookmarks
                doc.close()
            except Exception:
                meta["pages"] = 0
                meta["bookmarks"] = []

        results.append(meta)

    return results


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """Download a processed file by ID."""
    data = file_manager.get_bytes(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou expirado")

    info = file_manager.get_info(file_id)
    filename = info["filename"] if info else "download"
    content_type = info["content_type"] if info else "application/octet-stream"

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/metadata/{file_id}")
async def get_metadata(file_id: str):
    """Get metadata for an uploaded PDF."""
    data = file_manager.get_bytes(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    info = file_manager.get_info(file_id)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        toc = doc.get_toc(simple=False)
        bookmarks = [
            {"level": item[0], "title": item[1], "page": item[2]}
            for item in toc
        ]
        result = {
            "file_id": file_id,
            "filename": info["filename"] if info else "unknown",
            "pages": doc.page_count,
            "size_bytes": len(data),
            "bookmarks": bookmarks,
        }
        doc.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF inválido: {e}")


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a temporary file."""
    if file_manager.delete(file_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Arquivo não encontrado")
