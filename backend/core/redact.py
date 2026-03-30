import fitz
import re
from typing import List, Tuple

PATTERNS = {
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "cnpj": re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "date": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
}


def redact_text_matches(
    pdf_bytes: bytes,
    terms: List[str],
    ignore_case: bool = True,
    built_in_patterns: List[str] | None = None,
) -> Tuple[bytes, int]:
    """
    Localiza e aplica redação (tarja preta) em ocorrências de texto E padrões regex.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = 0
    built_in_patterns = built_in_patterns or []

    for page in doc:
        for term in terms:
            if not term:
                continue

            quads = []
            if ignore_case:
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

        if built_in_patterns:
            text = page.get_text("text")
            matches_found = set()
            for pat_key in built_in_patterns:
                regex = PATTERNS.get(pat_key)
                if regex:
                    for match in regex.findall(text):
                        if match not in matches_found:
                            matches_found.add(match)

            for match_text in matches_found:
                pattern_quads = page.search_for(match_text)
                if pattern_quads:
                    count += len(pattern_quads)
                    for quad in pattern_quads:
                        page.add_redact_annot(quad, text="", fill=(0, 0, 0))

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
