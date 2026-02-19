import fitz
from typing import Tuple, Dict, Any

def apply_bates_stamping(
    pdf_bytes: bytes,
    text_pattern: str = "Doc. {doc_idx} - Fls. {page_idx}",
    start_doc_idx: int = 1,
    start_page_idx: int = 1,
    position: str = "bottom_right", 
    margin: int = 20,
    font_size: int = 10,
    color: Tuple[float, float, float] = (0, 0, 0)
) -> bytes:
    """
    Aplica carimbo (Bates Numbering) nas páginas.
    position: top_left, top_center, top_right, bottom_left, bottom_center, bottom_right
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Mapeamento de posições para alinhamento e coordenadas
    # PyMuPDF coords: (0,0) is top-left.
    # Text alignment: 0=left, 1=center, 2=right
    
    for i, page in enumerate(doc):
        rect = page.rect
        w, h = rect.width, rect.height
        
        # Resolve texto dinâmico
        # Se tivéssemos múltiplos docs, start_doc_idx faria mais sentido no loop externo
        # Aqui assumimos um único PDF sendo carimbado, então doc_idx é fixo
        current_text = text_pattern.format(doc_idx=start_doc_idx, page_idx=start_page_idx + i)
        
        # Define ponto de inserção
        p = fitz.Point(0, 0)
        align = 0
        
        if "top" in position:
            y = margin + font_size
        else:
            y = h - margin
            
        if "left" in position:
            x = margin
            align = 0
        elif "center" in position:
            x = w / 2
            align = 1
        else: # right
            x = w - margin
            align = 2
            
        p = fitz.Point(x, y)
        
        # Insere texto
        page.insert_text(
            p,
            current_text,
            fontsize=font_size,
            fontname="tiro", # Times Roman standard
            color=color,
            align=align
        )
        
    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out
