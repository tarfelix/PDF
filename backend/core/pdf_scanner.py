import fitz
import re
from unidecode import unidecode
from config import LEGAL_KEYWORDS, PRE_SELECTED, LEGAL_REGEX_PATTERNS


def get_bookmark_ranges(doc: fitz.Document):
    """Extrai marcadores e calcula os intervalos de páginas que eles cobrem."""
    toc = doc.get_toc(simple=False)
    res = []
    for i, item in enumerate(toc):
        lvl, title, page1 = item[0], item[1], item[2]
        if not (1 <= page1 <= doc.page_count):
            continue

        start0 = page1 - 1
        end0 = doc.page_count - 1

        for j in range(i + 1, len(toc)):
            if toc[j][0] <= lvl:
                end0 = toc[j][2] - 2
                break

        end0 = max(start0, min(end0, doc.page_count - 1))
        disp = f"{'→' * (lvl - 1)}{'↪' if lvl > 1 else ''} {title} (Págs. {start0 + 1}-{end0 + 1})"

        res.append({
            "id": f"bm_{i}_{page1}",
            "display_text": disp,
            "start_page_0_idx": start0,
            "end_page_0_idx": end0,
            "title": title,
            "level": lvl,
            "source": "bookmark",
        })
    return res


def smart_scan(doc: fitz.Document):
    """
    Varre o conteúdo textual das páginas para identificar inícios de peças.
    Retorna lista de dicionários compatível com bookmarks.
    """
    bookmarks = get_bookmark_ranges(doc)
    if bookmarks and len(bookmarks) >= 3:
        return find_legal_sections(bookmarks)

    found_items = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if not text:
            continue

        header_text = text[:500]
        matched_cat = None

        for cat, patterns in LEGAL_REGEX_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, header_text):
                    matched_cat = cat
                    break
            if matched_cat:
                break

        if not matched_cat:
            lines = header_text.split("\n")
            first_lines = [l.strip().lower() for l in lines if l.strip()][:5]
            for l in first_lines:
                norm_line = unidecode(l)
                for cat, kws in LEGAL_KEYWORDS.items():
                    if any(k == norm_line or (len(k) > 4 and k in norm_line) for k in kws):
                        matched_cat = cat
                        break
                if matched_cat:
                    break

        if matched_cat:
            if (
                found_items
                and found_items[-1]["category"] == matched_cat
                and found_items[-1]["start_page_0_idx"] == page_num - 1
            ):
                pass
            else:
                found_items.append({
                    "id": f"scan_{page_num}",
                    "display_text": f"🔍 {matched_cat} (Pág. {page_num + 1})",
                    "start_page_0_idx": page_num,
                    "end_page_0_idx": doc.page_count - 1,
                    "title": matched_cat,
                    "category": matched_cat,
                    "unique_id": f"scan_{page_num}_{matched_cat}",
                    "preselect": True,
                    "source": "content_scan",
                })

    for i in range(len(found_items)):
        if i < len(found_items) - 1:
            found_items[i]["end_page_0_idx"] = found_items[i + 1]["start_page_0_idx"] - 1
            s = found_items[i]["start_page_0_idx"] + 1
            e = found_items[i]["end_page_0_idx"] + 1
            found_items[i]["display_text"] = f"🔍 {found_items[i]['title']} (Págs. {s}-{e})"

    return found_items


def find_legal_sections(bookmarks):
    """Identifica peças jurídicas nos marcadores baseando-se em palavras-chave."""
    out = []
    for i, bm in enumerate(bookmarks):
        norm = unidecode(bm["title"]).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({
                    **bm,
                    "category": cat,
                    "unique_id": f"legal_{i}_{bm['id']}",
                    "preselect": cat in PRE_SELECTED,
                    "source": "bookmark_filter",
                })
                break
    return out
