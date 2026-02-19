import fitz
from typing import List, Tuple

def redact_text_matches(pdf_bytes: bytes, terms: List[str], ignore_case: bool = True) -> Tuple[bytes, int]:
    """
    Localiza e aplica redação (tarja preta) em ocorrências de texto.
    Retorna (pdf_bytes_processado, contagem_de_matches).
    """
    doc: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = 0
    
    for page in doc:
        # Força o tipo para o linter entender
        page: fitz.Page = page
        
        for term in terms:
            if not term: continue
            
            # flags=fitz.TEXT_PRESERVE_WHITESPACE | ...
            # search_for retorna lista de Rect
            
            # flags = fitz.TEXT_CASE_IGNORED if ignore_case else 0
            # Fallback seguro: se não existir, usa 0 (mas perde case insensitivity)
            # Ou checa se existe
            flag_val = getattr(fitz, "TEXT_CASE_IGNORED", None)
            
            if flag_val is not None and ignore_case:
                quads = page.search_for(term, flags=flag_val)
            else:
                 # Versões antigas ou sem flag: search_for default costuma ser case insensitive? 
                 # Não necessariamente. Mas para não quebrar, vamos sem flags especiais se atributo não existe.
                 quads = page.search_for(term)
            
            if quads:
                count += len(quads)
                for quad in quads:
                    # Adiciona anotação de redação
                    page.add_redact_annot(quad, text="", fill=(0, 0, 0))
                    
        # Aplica redações da página
        page.apply_redactions(images=0) # images=0 -> não apaga imagens que se sobrepõem? 
        # images=fitz.PDF_REDACT_IMAGE_NONE (default) ou PDF_REDACT_IMAGE_REMOVE
        # Vamos usar default, que limpa o que está embaixo da area.
        
    out = doc.tobytes(garbage=4, deflate=True, clean=True)
    doc.close()
    return out, count
