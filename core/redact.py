import fitz
from typing import List, Tuple


def redact_text_matches(pdf_bytes: bytes, terms: List[str], ignore_case: bool = True) -> Tuple[bytes, int]:
    """
    Localiza e aplica redação (tarja preta) em ocorrências de texto.
    Retorna (pdf_bytes_processado, contagem_de_matches).
    
    Compatível com qualquer versão do PyMuPDF (sem dependência de flags experimentais).
    """
    doc: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = 0

    for page in doc:
        page: fitz.Page = page

        for term in terms:
            if not term:
                continue

            # Busca compatível: tenta com flag de case-insensitive quando disponível,
            # senão faz busca manual com variações de capitalização.
            quads = []

            # Tenta usar flag nativa (disponível no PyMuPDF >= 1.23.x em algumas builds)
            flag_val = getattr(fitz, "TEXT_CASE_IGNORED", None)
            if flag_val is None:
                # A constante pode ter outro nome dependendo da versão
                flag_val = getattr(fitz, "TEXT_DEHYPHENATE", None)  # só para testar existência
                flag_val = None  # Garantimos None

            if flag_val is not None and ignore_case:
                quads = page.search_for(term, flags=flag_val)
            elif ignore_case:
                # Fallback manual: busca o termo, lower e title case
                seen_rects = set()
                for variant in _case_variants(term):
                    for q in page.search_for(variant):
                        key = str(q)
                        if key not in seen_rects:
                            seen_rects.add(key)
                            quads.append(q)
            else:
                quads = page.search_for(term)

            if quads:
                count += len(quads)
                for quad in quads:
                    page.add_redact_annot(quad, text="", fill=(0, 0, 0))

        # Aplica todas as redações da página de uma vez
        page.apply_redactions(images=0)

    out = doc.tobytes(garbage=4, deflate=True, clean=True)
    doc.close()
    return out, count


def _case_variants(term: str) -> List[str]:
    """Gera variações de capitalização para busca manual."""
    variants = set()
    variants.add(term)
    variants.add(term.lower())
    variants.add(term.upper())
    variants.add(term.capitalize())
    variants.add(term.title())
    return list(variants)
