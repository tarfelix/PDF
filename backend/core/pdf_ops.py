import fitz
from typing import List, Optional, Tuple, Any, Dict
from core.utils import insert_pages


def optimize_pdf(doc: fitz.Document, options: Optional[Dict[str, Any]] = None) -> bytes:
    """Salva o documento com opções de otimização."""
    if options is None:
        options = {}
    save_opts: Dict[str, Any] = dict(garbage=4, deflate=True, clean=True)
    save_opts.update(options)
    return doc.tobytes(**save_opts)


def rotate_pages(pdf_bytes: bytes, rotations: Dict[int, int], optimize: bool = True) -> bytes:
    """Aplica rotação nas páginas especificadas."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_idx, angle in rotations.items():
        if 0 <= page_idx < doc.page_count:
            doc[page_idx].set_rotation(angle)
    opts: Dict[str, Any] = {"deflate_images": optimize, "deflate_fonts": optimize}
    return optimize_pdf(doc, opts)


def merge_pdfs(pdf_list: List[bytes], optimize: bool = True, password: Optional[str] = None) -> bytes:
    """Mescla uma lista de PDFs (bytes)."""
    merged = fitz.open()
    for pdf_bytes in pdf_list:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as src:
            merged.insert_pdf(src)

    opts: Dict[str, Any] = {"deflate_images": optimize, "deflate_fonts": optimize}

    if password:
        from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
        opts.update({
            "encryption": ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
            "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE,
        })

    return optimize_pdf(merged, opts)


def remove_pages(pdf_bytes: bytes, pages_to_remove: List[int], optimize: bool = True, password: Optional[str] = None) -> bytes:
    """Remove páginas especificadas de um PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    doc.delete_pages(pages_to_remove)

    opts: Dict[str, Any] = {"deflate_images": optimize, "deflate_fonts": optimize}
    if password:
        from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
        opts.update({
            "encryption": ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
            "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE,
        })

    return optimize_pdf(doc, opts)


def extract_pages(pdf_bytes: bytes, pages_to_extract: List[int], optimize: bool = True, password: Optional[str] = None) -> bytes:
    """Extrai páginas específicas para um novo PDF."""
    src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    new_doc = fitz.open()
    insert_pages(new_doc, src_doc, pages_to_extract)

    opts: Dict[str, Any] = {"deflate_images": optimize, "deflate_fonts": optimize}
    if password:
        from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
        opts.update({
            "encryption": ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
            "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE,
        })

    return optimize_pdf(new_doc, opts)


def split_pdf_by_count(pdf_bytes: bytes, pages_per_part: int, optimize: bool = True) -> List[Tuple[str, bytes]]:
    """Divide o PDF a cada N páginas."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    total_pages = doc.page_count

    for i in range(0, total_pages, pages_per_part):
        part_doc = fitz.open()
        rng = list(range(i, min(i + pages_per_part, total_pages)))
        insert_pages(part_doc, doc, rng)
        part_bytes = part_doc.tobytes(
            garbage=3, deflate=True, clean=True,
            deflate_images=optimize, deflate_fonts=optimize,
        )
        part_name_suffix = f"_parte_{i // pages_per_part + 1}"
        parts.append((part_name_suffix, part_bytes))
        part_doc.close()

    return parts


def split_pdf_by_size(pdf_bytes: bytes, max_mb: float, optimize: bool = True) -> List[Tuple[str, bytes]]:
    """Divide o PDF tentando respeitar um tamanho máximo em MB."""
    parts = []
    max_bytes = int(max_mb * 1024 * 1024)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    cur_doc = fitz.open()

    for p in range(doc.page_count):
        cur_doc.insert_pdf(doc, from_page=p, to_page=p)
        tmp_bytes = cur_doc.tobytes(garbage=1, deflate=True)

        if len(tmp_bytes) > max_bytes:
            if cur_doc.page_count > 1:
                final_part = fitz.open()
                final_part.insert_pdf(cur_doc, from_page=0, to_page=cur_doc.page_count - 2)
                parts.append((
                    f"_parte_{len(parts) + 1}",
                    final_part.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize, deflate_fonts=optimize),
                ))
                final_part.close()

                last_page_doc = fitz.open()
                last_page_doc.insert_pdf(cur_doc, from_page=cur_doc.page_count - 1, to_page=cur_doc.page_count - 1)
                cur_doc.close()
                cur_doc = last_page_doc
            else:
                parts.append((
                    f"_parte_{len(parts) + 1}",
                    cur_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize, deflate_fonts=optimize),
                ))
                cur_doc.close()
                cur_doc = fitz.open()

    if cur_doc.page_count > 0:
        parts.append((
            f"_parte_{len(parts) + 1}",
            cur_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize, deflate_fonts=optimize),
        ))
    cur_doc.close()
    return parts


def split_pdf_by_bookmarks(pdf_bytes: bytes, level: int = 1, optimize: bool = True) -> List[Tuple[str, bytes]]:
    """Divide o PDF pelos marcadores de nível especificado."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    toc = doc.get_toc(simple=False)
    parts = []

    splits = [(item[1], item[2] - 1) for item in toc if item[0] <= level]
    if not splits:
        return [("_completo", doc.tobytes(garbage=3, deflate=True, clean=True))]

    for i, (title, start_page) in enumerate(splits):
        end_page = splits[i + 1][1] - 1 if i + 1 < len(splits) else doc.page_count - 1
        part_doc = fitz.open()
        rng = list(range(start_page, end_page + 1))
        insert_pages(part_doc, doc, rng)
        from core.utils import safe_slug
        slug = safe_slug(title, maxlen=40)
        parts.append((
            f"_{slug}",
            part_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize, deflate_fonts=optimize),
        ))
        part_doc.close()

    return parts


def images_to_pdf(image_list: List[bytes], optimize: bool = True) -> bytes:
    """Converte lista de imagens (bytes) em um único PDF."""
    doc = fitz.open()
    for img_bytes in image_list:
        with fitz.open(stream=img_bytes) as img_doc:
            pdf_bytes = img_doc.convert_to_pdf()
            with fitz.open("pdf", pdf_bytes) as pdf_page:
                doc.insert_pdf(pdf_page)

    opts: Dict[str, Any] = {"deflate_images": optimize, "deflate_fonts": optimize}
    return optimize_pdf(doc, opts)
