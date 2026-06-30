"""Garante que `backend/` esteja no sys.path para imports estilo `from auth import ...`
(o app roda com cwd=backend/, sem pacote `backend.*` — ver backend/main.py)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
