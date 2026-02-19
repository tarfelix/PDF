import fitz
from unidecode import unidecode
from config import LEGAL_KEYWORDS, PRE_SELECTED

def get_bookmark_ranges(doc: fitz.Document):
    """Extrai marcadores e calcula os intervalos de páginas que eles cobrem."""
    toc = doc.get_toc(simple=False)
    res = []
    # Estrutura do toc: [lvl, title, page, ...]
    for i, item in enumerate(toc):
        lvl, title, page1 = item[0], item[1], item[2]
        
        # Validação básica de página
        if not (1 <= page1 <= doc.page_count): continue
        
        start0 = page1 - 1
        end0 = doc.page_count - 1 # Default até o fim
        
        # Procura o próximo marcador de mesmo nível ou superior para definir o fim
        for j in range(i + 1, len(toc)):
            if toc[j][0] <= lvl:
                end0 = toc[j][2] - 2 # Página anterior ao próximo marcador
                break
        
        # Ajuste de limites
        end0 = max(start0, min(end0, doc.page_count - 1))
        
        disp = f"{'➡️'*(lvl-1)}{'↪️' if lvl>1 else ''} {title} (Págs. {start0+1}-{end0+1})"
        
        res.append({
            "id": f"bm_{i}_{page1}",
            "display_text": disp,
            "start_page_0_idx": start0,
            "end_page_0_idx": end0,
            "title": title,
            "level": lvl
        })
    return res

def find_legal_sections(bookmarks):
    """Identifica peças jurídicas nos marcadores baseando-se em palavras-chave."""
    out = []
    for i, bm in enumerate(bookmarks):
        norm = unidecode(bm['title']).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({
                    **bm,
                    'category': cat,
                    'unique_id': f"legal_{i}_{bm['id']}",
                    'preselect': cat in PRE_SELECTED
                })
                break
    return out
