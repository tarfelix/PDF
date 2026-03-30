import os
import time
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

TEMP_DIR = Path(os.environ.get("TEMP_DIR", "/tmp/pdf-editor"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class FileManager:
    """Manages temporary files with auto-cleanup."""

    def __init__(self):
        self._files: dict[str, dict] = {}

    def store(self, data: bytes, filename: str, content_type: str = "application/pdf") -> str:
        """Store bytes to a temp file and return a file_id."""
        file_id = uuid.uuid4().hex[:12]
        ext = Path(filename).suffix or ".pdf"
        path = TEMP_DIR / f"{file_id}{ext}"
        path.write_bytes(data)
        self._files[file_id] = {
            "path": str(path),
            "filename": filename,
            "content_type": content_type,
            "created_at": time.time(),
            "size": len(data),
        }
        return file_id

    def get_bytes(self, file_id: str) -> Optional[bytes]:
        """Read file bytes by ID."""
        info = self._files.get(file_id)
        if not info:
            return None
        path = Path(info["path"])
        if not path.exists():
            del self._files[file_id]
            return None
        return path.read_bytes()

    def get_info(self, file_id: str) -> Optional[dict]:
        """Get file metadata by ID."""
        return self._files.get(file_id)

    def delete(self, file_id: str) -> bool:
        """Delete a file by ID."""
        info = self._files.pop(file_id, None)
        if not info:
            return False
        path = Path(info["path"])
        if path.exists():
            path.unlink()
        return True

    def cleanup_expired(self):
        """Remove files older than TTL."""
        ttl_seconds = settings.temp_file_ttl_minutes * 60
        now = time.time()
        expired = [
            fid for fid, info in self._files.items()
            if now - info["created_at"] > ttl_seconds
        ]
        for fid in expired:
            self.delete(fid)
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired files")

    async def cleanup_loop(self):
        """Background loop that cleans up expired files."""
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            self.cleanup_expired()


file_manager = FileManager()
