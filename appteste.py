"""
pdf_editor_ptbr_streamlit.py
Editor e Divisor de PDF Completo (PT-BR) – versão consolidada
-------------------------------------------------------------
• Compatível PyMuPDF ≥ 1.23 (parâmetro subpages)
• Helper insert_pages() retro-compatível (pages/subpages)
• initialize_session_state() com deepcopy e limpeza de chaves dinâmicas
• @st.cache_resource para miniaturas; @st.cache_data para metadados
• Palavras-chave jurídicas ampliadas + unidecode
• Proteção para não excluir todas as páginas
• Refatoração parcial para clareza, mas tudo em um só arquivo para facilitar cópia/execução
"""

# ===========================================================
# IMPORTS E CONFIG
# ===========================================================
import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
from PIL import Image
import os
import copy
from itertools import islice
from unidecode import unidecode

st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")

# ===========================================================
# HELPERS DE COMPATIBILIDADE
# ===========================================================

def insert_pages(dst: fitz.Document, src: fitz.Document, pages: list[int]):
    """Insere lista de páginas 0-based de *src* em *dst* sem falhar em versões antigas."""
    try:
        dst.insert_pdf(src, subpages=pages)  # ≥ 1.23
    except TypeError:
        try:
            dst.insert_pdf(src, pages=pages)  # 1.19 – 1.22
        except TypeError:
            # fallback: página a página
            for p in pages:
                dst.insert_pdf(src, from_page=p, to_page=p)

# ===========================================================
# ESTADO DA SESSÃO
# ===========================================================
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 'processed_pdf_bytes_legal': None,
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_merge': None, 'processed_pdf_bytes_optimize': None,
    'split_pdf_parts': [], 'error_message': None, 'last_uploaded_file_ids': [],
    'page_previews': [], 'visual_page_selection': {}, 'files_to_merge': [],
    'processing_remove': False, 'processing_split': False, 'processing_extract': False, 'processing_legal_extract': False,
    'processing_visual_delete': False, 'processing_visual_extract': False,
    'processing_merge': False, 'processing_optimize': False,
    'active_tab_visual_preview_ready': False, 'generating_previews': False,
    'current_page_count_for_inputs': 0, 'is_single_pdf_mode': False, 'visual_action_type': None,
    'bookmark_search_term_remove': "", 'bookmark_search_term_extract': "", 'found_legal_pieces': [],
}

def initialize_session_state():
    """Reseta seletivamente o estado da aplicação."""
    # remove chaves dinâmicas geradas por checkboxes e botões
    dyn = [k for k in st.session_state.keys() if k.startswith((
        "delete_bookmark_", "extract_bookmark_", "select_page_preview_", "legal_piece_", "up_", "down_")) or
        k.endswith(("_input", "_checkbox"))]
    for k in dyn:
        st.session_state.pop(k, None)
    # recria defaults
    for k, v in DEFAULT_STATE.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(v)

if 'initialized_once' not in st.session_state:
    initialize_session_state()
    st.session_state.initialized_once = True

# ===========================================================
# PALAVRAS-CHAVE JURÍDICAS
# ===========================================================
LEGAL_KEYWORDS = {
    "Petição Inicial": ['petição inicial', 'inicial'],
    "Defesa/Contestação": ['defesa', 'contestação', 'contestacao'],
    "Réplica": ['réplica', 'replica', 'impugnação à contestação', 'impugnacao a contestacao'],
    "Sentença": ['sentença', 'sentenca'],
    "Acórdão": ['acórdão', 'acordao'],
    "Decisão": ['decisão', 'decisao', 'decisão interlocutória', 'decisao interlocutoria'],
    "Despacho": ['despacho'],
    "Recurso": ['recurso', 'agravo', 'embargos', 'apelação', 'apelacao'],
    "Ata de Audiência": ['ata de audiência', 'ata de audiencia', 'termo de audiência', 'termo de audiencia'],
    "Laudo": ['laudo', 'parecer técnico', 'parecer tecnico'],
    "Manifestação": ['manifestação', 'manifestacao', 'petição', 'peticao'],
    "Documento": ['documento'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'indice', 'sumário', 'sumario'],
}

PRE_SELECTED_LEGAL_CATEGORIES = [
    "Petição Inicial", "Sentença", "Acórdão", "Decisão", "Despacho",
    "Defesa/Contestação", "Réplica", "Recurso", "Ata de Audiência",
    "Laudo", "Manifestação"
]

# ===========================================================
# FUNÇÕES DE PDF CACHADAS
# ===========================================================
@st.cache_resource(show_spinner=False)
def build_previews(pdf_bytes: bytes, dpi=48):
    """Gera miniaturas PNG de todas as páginas (dpi baixo)."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        mtx = fitz.Matrix(dpi/72, dpi/72)
        return [pg.get_pixmap(matrix=mtx).tobytes("png") for pg in doc]

@st.cache_data(max_entries=5)
def get_pdf_metadata(pdf_bytes: bytes, name="pdf"):
    """Retorna (bookmarks, n_pages, erro) de um PDF em bytes."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            bms = get_bookmark_ranges(d)
            return bms, d.page_count, None
    except Exception as e:
        return [], 0, f"Erro ao ler {name}: {e}"

def get_bookmark_ranges(doc: fitz.Document):
    """Converte TOC em lista de dicionários com intervalo de páginas."""
    toc = doc.get_toc(simple=False)
    res = []
    total = doc.page_count
    for i, (lvl, title, page1, *_) in enumerate(toc):
        if not 1 <= page1 <= total:
            continue
        start0 = page1 - 1
        end0 = total - 1
        for j in range(i+1, len(toc)):
            lvl_j, _, page_j, *_ = toc[j]
            if lvl_j <= lvl:
                end0 = page_j - 2
                break
        end0 = max(start0, min(end0, total-1))
        disp = f"{'➡️'*(lvl-1)}{'↪️' if lvl>1 else ''} {title} (Págs. {start0+1}-{end0+1})"
        res.append({
            "id": f"bm_{i}_{page1}", "level": lvl, "title": title,
            "start_page_0_idx": start0, "end_page_0_idx": end0, "display_text": disp,
        })
    return res

def find_legal_sections(bms):
    """Classifica marcadores em categorias jurídicas."""
    out = []
    for i, bm in enumerate(bms):
        norm = unidecode(bm['title']).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({**bm,
                            'category': cat,
                            'unique_id': f"legal_{i}_{bm['id']}",
                            'preselect': cat in PRE_SELECTED_LEGAL_CATEGORIES})
                break
    return out

def parse_page_input(inp: str, max1: int):
    """Converte input tipo '1,3-5' em lista de índices 0-based."""
    sel = set()
    if not inp:
        return []
    for part in inp.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if '-' in part:
                a, b = map(int, part.split('-'))
                if a > b:
                    a, b = b, a
                sel.update(i-1 for i in range(a, b+1) if 1 <= i <= max1)
            else:
                p = int(part)
                if 1 <= p <= max1:
                    sel.add(p-1)
        except ValueError:
            st.warning(f"Entrada inválida: '{part}'")
    return sorted(sel)

# ===========================================================
# INTERFACE DE USUÁRIO
# ===========================================================
st.title("✂️ Editor e Divisor de PDF Completo (PT-BR)")
st.markdown("Carregue um ou mais PDFs e escolha a ação desejada nas abas.")

st.sidebar.button("🔄 Limpar Tudo", on_click=initialize_session_state)

uploaded = st.file_uploader("📄 Carregue PDF(s)", type="pdf", accept_multiple_files=True)

doc_cached = None  # handler para o PDF principal (modo single)

# ---------------- Processa upload -----------------
if uploaded:
    ids = sorted(f.file_id for f in uploaded)
    if ids != st.session_state.last_uploaded_file_ids:
        initialize_session_state()
        st.session_state.last_uploaded_file_ids = ids
        if len(uploaded) == 1:
            st.session_state.is_single_pdf_mode = True
            st.session_state.pdf_doc_bytes_original = uploaded[0].getvalue()
            st.session_state.pdf_name = uploaded[0].name
            bms, pages, err = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, uploaded[0].name)
            if err:
                st.error(err); st.session_state.is_single_pdf_mode = False
            else:
                st.session_state.bookmarks_data = bms
                st.session_state.current_page_count_for_inputs = pages
                st.session_state.found_legal_pieces = find_legal_sections(bms)
        else:
            st.session_state.files_to_merge = uploaded
        st.experimental_rerun()

# ------------- Tabs Dinâmicos --------------------
tabs = ["Mesclar"]
if st.session_state.is_single_pdf_mode:
    tabs += ["Peças", "Visual", "Remover", "Extrair", "Dividir", "Otimizar"]

TAB = st.tabs(tabs)

# ===========================================================
# TAB Mesclar
# ===========================================================
with TAB[0]:
    st.header("Mesclar PDFs")
    if not st.session_state.files_to_merge and not st.session_state.is_single_pdf_mode:
        st.info("Selecione dois ou mais arquivos para mesclar.")
    elif st.session_state.files_to_merge:
        def move(i, delta):
            lst = st.session_state.files_to_merge
            lst[i+delta], lst[i] = lst[i], lst[i+delta]
        for i, f in enumerate(st.session_state.files_to_merge):
            c_up, c_down, c_lbl = st.columns([0.1, 0.1, 0.8])
            if i: c_up.button("⬆️", key=f"up{i}", on_click=move, args=(i, -1))
            if i < len(st.session_state.files_to_merge)-1: c_down.button("⬇️", key=f"dn{i}", on_click=move, args=(i, 1))
            c_lbl.write(f"{i+1}. {f.name} ({round(f.size/1_048_576,2)} MB)")
        optimize = st.checkbox("Otimizar resultado", value=True)
        if st.button("Mesclar agora"):
            st.session_state.processing_merge = True
            merged = fitz.open()
            try:
                for f in st.session_state.files_to_merge:
                    with fitz.open(stream=f.getvalue(), filetype="pdf") as d:
                        merged.insert_pdf(d)
                buf = io.BytesIO()
                save_opt = dict(garbage=4, deflate=True, clean=True,
                                deflate_images=optimize, deflate_fonts=optimize)
                merged.save(buf, **save_opt)
                st.download_button("⬇️ Baixar", buf.getvalue(), "mesclado.pdf", "application/pdf")
                st.success("PDFs mesclados com sucesso!")
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                merged.close()
                st.session_state.processing_merge = False

# ===========================================================
# Aba únicas (necessitam doc)
# ===========================================================
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    doc_cached = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")

    # -------------- TAB Peças Jurídicas --------------
    with TAB[1]:
        st.header("Extrair Peças Jurídicas (Marcadores)")
        pcs = st.session_state.found_legal_pieces
        if not pcs:
            st.warning("Nenhuma peça reconhecida.")
        else:
            col1, col2, col3 = st.columns(3)
            if col1.button("Selecionar todas"):
                for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = True
            if col2.button("Limpar seleção"):
                for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = False
            if col3.button("Restaurar pré-seleção"):
                for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = p['preselect']
            st.divider()
            with st.container(height=350):
                for p in pcs:
                    key = f"legal_piece_{p['unique_id']}"
                    if key not in st.session_state:
                        st.session_state[key] = p['preselect']
                    st.checkbox(f"**{p['category']}** – {p['title']}  "
                                f"(págs. {p['start_page_0_idx']+1}-{p['end_page_0_idx']+1})",
                                key=key)
            optimize = st.checkbox("Otimizar ao salvar", value=True)
            if st.button("Extrair peças selecionadas"):
                sel_pages = set()
                for p in pcs:
                    if st.session_state.get(f"legal_piece_{p['unique_id']}"):
                        sel_pages.update(range(p['start_page_0_idx'], p['end_page_0_idx']+1))
                if not sel_pages:
                    st.warning("Nada selecionado.")
                else:
                    new_doc = fitz.open()
                    insert_pages(new_doc, doc_cached, sorted(sel_pages))
                    buf = io.BytesIO()
                    new_doc.save(buf, garbage=4, deflate=True, clean=True,
                                 deflate_images=optimize, deflate_fonts=optimize)
                    st.download_button("⬇️ Baixar", buf.getvalue(),
                                       f"{os.path.splitext(st.session_state.pdf_name)[0]}_pecas.pdf",
                                       "application/pdf")
                    st.success("PDF gerado!")
                    new_doc.close()

    # -------------- TAB Visual --------------
    with TAB[2]:
        st.header("Gerir páginas visualmente")
        if not st.session_state.active_tab_visual_preview_ready:
            st.info("Gerando miniaturas … aguarde.")
            st.session_state.page_previews = build_previews(st.session_state.pdf_doc_bytes_original)
            st.session_state.active_tab_visual_preview_ready = True
        n_cols = st.sidebar.slider("Colunas", 2, 8, 4)
        cols = st.columns(n_cols)
        for i, img in enumerate(st.session_state.page_previews):
            col = cols[i % n_cols]
            if i not in st.session_state.visual_page_selection:
                st.session_state.visual_page_selection[i] = False
            st.image(img, width=120)
            st.session_state.visual_page_selection[i] = col.checkbox(
                f"Pág {i+1}", value=st.session_state.visual_page_selection[i],
                label_visibility="collapsed")
        sel = sorted([i for i, v in st.session_state.visual_page_selection.items() if v])
        st.sidebar.write(f"Páginas selecionadas: **{len(sel)}**")
        col_del, col_ext = st.columns(2)
        if col_del.button("Excluir selecionadas") and sel:
            if len(sel) >= doc_cached.page_count:
                st.error("Precisa sobrar ao menos uma página.")
            else:
                mod = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                mod.delete_pages(sel)
                buf = io.BytesIO(); mod.save(buf, garbage=4, deflate=True, clean=True)
                st.download_button("⬇️ Baixar", buf.getvalue(), "excluido_visual.pdf", "application/pdf")
        if col_ext.button("Extrair selecionadas") and sel:
            ext_doc = fitz.open(); insert_pages(ext_doc, doc_cached, sel)
            buf = io.BytesIO(); ext_doc.save(buf, garbage=4, deflate=True, clean=True)
            st.download_button("⬇️ Baixar", buf.getvalue(), "extraido_visual.pdf", "application/pdf")

    # -------------- TAB Remover --------------
    with TAB[3]:
        st.header("Remover páginas")
        bm_term = st.text_input("Filtrar marcadores")
        to_del = set()
        if st.session_state.bookmarks_data:
            for bm in st.session_state.bookmarks_data:
                if not bm_term or bm_term.lower() in bm['display_text'].lower():
                    if st.checkbox(bm['display_text'], key=f"del_{bm['id']}"):
                        to_del.update(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1))
        dir_pages = parse_page_input(
            st.text_input("Números de página (ex. 1,3-5)", key="del_nums"),
            doc_cached.page_count)
        to_del.update(dir_pages)
        optimize_rem = st.checkbox("Otimizar ao salvar", value=True)
        if st.button("Remover páginas") and to_del:
            if len(to_del) >= doc_cached.page_count:
                st.error("Não exclua todas as páginas.")
            else:
                mod = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                mod.delete_pages(sorted(to_del))
                buf = io.BytesIO(); mod.save(buf, garbage=4, deflate=True, clean=True,
                                             deflate_images=optimize_rem, deflate_fonts=optimize_rem)
                st.download_button("⬇️ Baixar", buf.getvalue(), "removido.pdf", "application/pdf")

    # -------------- TAB Extrair ----------------
    with TAB[4]:
        st.header("Extrair páginas")
        bm_term_e = st.text_input("Filtrar marcadores", key="ext_bm_filter")
        to_ext = set()
        if st.session_state.bookmarks_data:
            for bm in st.session_state.bookmarks_data:
                if not bm_term_e or bm_term_e.lower() in bm['display_text'].lower():
                    if st.checkbox(bm['display_text'], key=f"ext_{bm['id']}"):
                        to_ext.update(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1))
        dir_pages_e = parse_page_input(
            st.text_input("Números de página (ex. 1,3-5)", key="ext_nums"),
            doc_cached.page_count)
        to_ext.update(dir_pages_e)
        optimize_ext = st.checkbox("Otimizar ao salvar", value=True)
        if st.button("Extrair páginas") and to_ext:
            ext_doc = fitz.open(); insert_pages(ext_doc, doc_cached, sorted(to_ext))
            buf = io.BytesIO(); ext_doc.save(buf, garbage=4, deflate=True, clean=True,
                                             deflate_images=optimize_ext, deflate_fonts=optimize_ext)
            st.download_button("⬇️ Baixar", buf.getvalue(), "extraido.pdf", "application/pdf")

    # -------------- TAB Dividir --------------
    with TAB[5]:
        st.header("Dividir PDF")
        mode = st.radio("Método", ("Por tamanho (MB)", "A cada N páginas"))
        optimize_split = st.checkbox("Otimizar partes", value=True)
        parts = []
        if mode == "Por tamanho (MB)":
            max_mb = st.number_input("Tamanho máx. por parte (MB)", min_value=0.1, value=5.0, step=0.1)
            if st.button("Dividir"):
                tgt = max_mb * 1024 * 1024
                cur = 0
                while cur < doc_cached.page_count:
                    part_doc = fitz.open()
                    for p in range(cur, doc_cached.page_count):
                        trial = fitz.open(); insert_pages(trial, doc_cached, list(range(cur, p+1)))
                        if trial.sum_file_size() > tgt and p > cur:
                            break
                        part_doc.close(); part_doc = trial
                    buf = io.BytesIO()
                    part_doc.save(buf, garbage=3, deflate=True, clean=True,
                                  deflate_images=optimize_split, deflate_fonts=optimize_split)
                    parts.append((f"parte_{len(parts)+1}.pdf", buf.getvalue()))
                    cur += part_doc.page_count
                if parts:
                    zbuf = io.BytesIO()
                    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as z:
                        for name, data in parts:
                            z.writestr(name, data)
                    zbuf.seek(0)
                    st.download_button("⬇️ Baixar ZIP", zbuf.getvalue(), "partes.zip", "application/zip")
        else:
            n = st.number_input("N páginas por parte", min_value=1, value=10)
            if st.button("Dividir"):
                for i in range(0, doc_cached.page_count, n):
                    part_doc = fitz.open()
                    insert_pages(part_doc, doc_cached, list(range(i, min(i+n, doc_cached.page_count))))
                    buf = io.BytesIO()
                    part_doc.save(buf, garbage=3, deflate=True, clean=True,
                                  deflate_images=optimize_split, deflate_fonts=optimize_split)
                    parts.append((f"parte_{len(parts)+1}.pdf", buf.getvalue()))
                if parts:
                    zbuf = io.BytesIO()
                    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as z:
                        for name, data in parts:
                            z.writestr(name, data)
                    zbuf.seek(0)
                    st.download_button("⬇️ Baixar ZIP", zbuf.getvalue(), "partes.zip", "application/zip")

    # -------------- TAB Otimizar --------------
    with TAB[6]:
        st.header("Otimizar PDF")
        prof = st.selectbox("Perfil", ("Leve", "Recomendada", "Máxima"), index=1)
        if st.button("Otimizar"):
            doc_opt = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
            opt = dict(clean=True)
            if prof == "Leve":
                opt.update(garbage=2, deflate=True)
            elif prof == "Recomendada":
                opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
            elif prof == "Máxima":
                opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
            buf = io.BytesIO()
            doc_opt.save(buf, **opt)
            st.download_button("⬇️ Baixar", buf.getvalue(), "otimizado.pdf", "application/pdf")
            st.success("PDF otimizado!")

# ===========================================================
# FOOTER
# ===========================================================
if st.session_state.error_message:
    st.sidebar.error(st.session_state.error_message)
