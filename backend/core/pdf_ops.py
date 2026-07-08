import fitz
from typing import List, Optional, Tuple, Any, Dict
from core.utils import insert_pages


# Filtros que já são eficientes (ou não-foto) — recomprimir em JPEG pioraria.
_SKIP_IMAGE_FILTERS = {"CCITTFaxDecode", "JBIG2Decode", "JPXDecode"}


def recompress_images(doc: fitz.Document, jpeg_quality: int = 75, max_dim: int = 1700) -> int:
    """Reamostra e reencoda em JPEG as imagens grandes do documento.

    O `deflate` do PyMuPDF não reduz imagens já comprimidas (JPEG). Em PDFs
    escaneados as imagens dominam o tamanho, então a única forma de reduzir é
    recomprimir/reamostrar. Preserva texto e estrutura — só troca os streams
    de imagem. Retorna a quantidade de imagens efetivamente recomprimidas.
    """
    replaced = 0
    seen: set = set()
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)

            bpc = img[4]
            img_filter = img[8]
            # Pula imagens 1-bit (fax/preto-e-branco) e formatos já eficientes.
            if bpc == 1 or img_filter in _SKIP_IMAGE_FILTERS:
                continue

            try:
                old_len = len(doc.xref_stream_raw(xref) or b"")
            except Exception:
                old_len = 0

            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue

            try:
                # Normaliza CMYK/alpha para RGB (JPEG não suporta alpha/CMYK aqui).
                if pix.alpha or (pix.colorspace is not None and pix.n - pix.alpha >= 4):
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                # Reamostra reduzindo pela metade até caber em max_dim (shrink só halva).
                while max(pix.width, pix.height) > max_dim and pix.width > 4 and pix.height > 4:
                    pix.shrink(1)

                new_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_quality)
            except Exception:
                pix = None
                continue
            finally:
                pix = None

            # Só substitui se realmente reduzir.
            if old_len and len(new_bytes) >= old_len:
                continue

            try:
                page.replace_image(xref, stream=new_bytes)
                replaced += 1
            except Exception:
                continue

    return replaced


def optimize_pdf(doc: fitz.Document, options: Optional[Dict[str, Any]] = None) -> bytes:
    """Salva o documento com opções de otimização."""
    if options is None:
        options = {}
    options = dict(options)

    # Recompressão de imagens (separada das opções de save do PyMuPDF).
    recompress = options.pop("recompress_images", False)
    jpeg_quality = options.pop("jpeg_quality", 75)
    max_dim = options.pop("max_image_dim", 1700)
    if recompress:
        recompress_images(doc, jpeg_quality=jpeg_quality, max_dim=max_dim)

    save_opts: Dict[str, Any] = dict(garbage=4, deflate=True, clean=True)
    save_opts.update(options)
    # MuPDF removeu suporte a linearização ("Linearisation is no longer supported").
    save_opts.pop("linear", None)
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
