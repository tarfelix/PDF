import re
from unidecode import unidecode
from typing import List
import fitz

def safe_slug(text: str, maxlen: int = 60) -> str:
    """Gera um slug seguro para nomes de arquivos."""
    s = unidecode(text).strip().lower()
    s = re.sub(r"[^a-z0-9\-\_\s\.]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return (s or "arquivo")[:maxlen]

def parse_page_input(inp: str, max_pages: int) -> List[int]:
    """Converte string de entrada (ex: '1, 3-5') em lista de índices zero-based."""
    sel = set()
    if not inp: return []
    for part in inp.split(','):
        part = part.strip()
        try:
            if '-' in part:
                a, b = map(int, part.split('-'))
                if a > b: a, b = b, a
                sel.update(i - 1 for i in range(a, b + 1) if 1 <= i <= max_pages)
            else:
                p = int(part)
                if 1 <= p <= max_pages: sel.add(p - 1)
        except ValueError:
            pass # Ignora entradas inválidas silenciosamente ou poderia logar
    return sorted(sel)

def insert_pages(dst: fitz.Document, src: fitz.Document, pages: List[int]):
    """Insere páginas de um documento em outro, lidando com diferenças de versão do PyMuPDF."""
    try:
        dst.insert_pdf(src, subpages=pages)
    except TypeError:
        try:
            dst.insert_pdf(src, pages=pages)
        except TypeError:
            for p in pages:
                dst.insert_pdf(src, from_page=p, to_page=p)
