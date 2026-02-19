import streamlit as st
import io
import os
import copy
from config import DEFAULT_BRAND, VISUAL_PREVIEW_SIZE_LIMIT_MB
from ui.components import brand_header, get_pdf_metadata_cached, get_pdf_document

# Import dinâmico das abas
from ui.tabs import merge, split, visual, remove, extract, legal, optimize, bates, converter, redact, diff

# --- Configuração Inicial ---
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF — v3")

# --- Estado da Sessão ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 
    'pdf_name': None, 
    'bookmarks_data': [],
    'last_uploaded_file_ids': [], 
    'page_previews': [],
    'visual_page_selection': {}, 
    'visual_custom_order': [],
    'files_to_merge': [], 
    'found_legal_pieces': [],
    'is_single_pdf_mode': False, 
    'visual_tab_enabled': False,
    'brand': DEFAULT_BRAND.copy(), 
    'brand_high_contrast': False, 
    'show_logo': True,
}

def initialize_session_state():
    """Reseta o estado da sessão."""
    dyn = [k for k in st.session_state.keys()
           if k.startswith(("delete_bookmark_", "extract_bookmark_", "select_page_preview_",
                            "legal_piece_", "marker_piece_", "up_", "down_", "reord_", "visual_rotations"))
           or k.endswith(("_input", "_checkbox"))]
    for k in dyn: st.session_state.pop(k, None)
    
    for k, v in DEFAULT_STATE.items():
        if k == "brand":
            st.session_state[k] = DEFAULT_BRAND.copy()
        else:
            st.session_state[k] = copy.deepcopy(v)

def _file_key(f):
    if hasattr(f, "file_id"): return f.file_id
    if hasattr(f, "id"): return f.id
    return f"{getattr(f,'name','arquivo')}-{getattr(f,'size',0)}"

if 'initialized_once' not in st.session_state:
    initialize_session_state()
    st.session_state.initialized_once = True

# --- Sidebar ---
with st.sidebar:
    st.subheader("🎨 Aparência")
    st.session_state.brand_high_contrast = st.toggle("Modo alto contraste", value=st.session_state.get('brand_high_contrast', False))
    st.session_state.show_logo = st.checkbox("Mostrar logo no topo", value=st.session_state.get('show_logo', True))
    
    with st.expander("Identidade Visual (cores/logo)"):
        brand = st.session_state.get('brand', DEFAULT_BRAND.copy())
        brand['name'] = st.text_input("Nome (header)", value=brand.get('name', DEFAULT_BRAND['name']))
        brand['logo_url'] = st.text_input("URL do logo (PNG/SVG)", value=brand.get('logo_url', DEFAULT_BRAND['logo_url']))
        
        c1, c2 = st.columns(2)
        brand['primary'] = c1.color_picker("Primária", brand.get('primary', DEFAULT_BRAND['primary']))
        brand['secondary'] = c2.color_picker("Secundária", brand.get('secondary', DEFAULT_BRAND['secondary']))
        
        c3, c4 = st.columns(2)
        brand['accent'] = c3.color_picker("Acento", brand.get('accent', DEFAULT_BRAND['accent']))
        brand['bg_light'] = c4.color_picker("Fundo claro", brand.get('bg_light', DEFAULT_BRAND['bg_light']))
        
        brand['subtitle'] = st.text_input("Subtítulo", value=brand.get('subtitle', DEFAULT_BRAND['subtitle']))
        st.session_state.brand = brand
        
    st.divider()
    st.button("🔄 Limpar Tudo e Recomeçar", on_click=initialize_session_state, type="primary")
    st.caption("Dica: proteja o PDF com senha nas operações que oferecem este campo.")

# --- Header ---
brand_header(st.session_state.brand, st.session_state.brand_high_contrast)

st.title("✂️ Editor e Divisor de PDF — v3")
st.write("Carregue um ou mais PDFs. Arquivos **> 50 MB** desativam a aba **Visual** (miniaturas).")

uploaded_files = st.file_uploader("📄 Carregue seu(s) PDF(s)", type="pdf", accept_multiple_files=True)

# --- Processamento de Upload ---
if uploaded_files:
    file_ids = sorted(_file_key(f) for f in uploaded_files)
    if file_ids != st.session_state.last_uploaded_file_ids:
        initialize_session_state()
        st.session_state.last_uploaded_file_ids = file_ids
        
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            f = uploaded_files[0]
            size_mb = f.size / (1024 * 1024)
            
            st.session_state.visual_tab_enabled = size_mb <= VISUAL_PREVIEW_SIZE_LIMIT_MB
            if not st.session_state.visual_tab_enabled:
                st.warning(f"⚠️ Arquivo grande ({size_mb:.1f} MB). A aba 'Visual' foi desabilitada.")
                
            st.session_state.pdf_doc_bytes_original = f.getvalue()
            st.session_state.pdf_name = f.name
            
            bms, pages, err = get_pdf_metadata_cached(st.session_state.pdf_doc_bytes_original, f.name)
            if err:
                st.error(err)
                st.session_state.is_single_pdf_mode = False
            else:
                st.session_state.bookmarks_data = bms
                st.info(f"PDF '{f.name}' ({pages} páginas) carregado. Use as abas abaixo.")
        else:
            st.session_state.is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files
            st.info(f"{len(uploaded_files)} arquivos carregados. Vá para a aba 'Mesclar'.")
        
        st.rerun()

# --- Definição de Abas ---
tabs = []
if st.session_state.get('is_single_pdf_mode', False):
    tabs.append("Peças Jurídicas")
    tabs.append("Numeração (Bates)")
    tabs.append("Redação (Tarja)")
    if st.session_state.get('visual_tab_enabled', False):
        tabs.append("Visual")
    tabs += ["Remover", "Extract", "Dividir", "Otimizar"]
elif not st.session_state.get('files_to_merge', []):
    tabs.append("Converter Imagens")
    tabs.append("Comparar Versões")

tabs.append("Mesclar")

tab_objs = st.tabs(tabs)
from typing import Dict, Any
tab_map: Dict[str, Any] = {name: tab for name, tab in zip(tabs, tab_objs)}

# --- Carregamento do Documento (Cache) ---
doc_cached = None
if st.session_state.get('is_single_pdf_mode', False) and st.session_state.pdf_doc_bytes_original:
    doc_cached = get_pdf_document(st.session_state.pdf_doc_bytes_original)
    if not doc_cached:
        st.error("PDF inválido/corrompido.")
        st.stop()

# --- Renderização das Abas ---

if "Mesclar" in tab_map:
    with tab_map["Mesclar"]:
        merge.render(st.session_state.get('files_to_merge', []))
        
if "Converter Imagens" in tab_map:
    with tab_map["Converter Imagens"]:
        converter.render()
        
if "Comparar Versões" in tab_map:
    with tab_map["Comparar Versões"]:
        diff.render()

if st.session_state.get('is_single_pdf_mode') and doc_cached:
    if "Peças Jurídicas" in tab_map:
        with tab_map["Peças Jurídicas"]:
            legal.render(doc_cached, st.session_state.pdf_name, bookmarks_unused=st.session_state.bookmarks_data, pdf_bytes_original=st.session_state.pdf_doc_bytes_original)

    if "Numeração (Bates)" in tab_map:
        with tab_map["Numeração (Bates)"]:
            bates.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)

    if "Redação (Tarja)" in tab_map:
        with tab_map["Redação (Tarja)"]:
            redact.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)

    if "Visual" in tab_map:
        with tab_map["Visual"]:
            visual.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)

    if "Remover" in tab_map:
        with tab_map["Remover"]:
            remove.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name, st.session_state.bookmarks_data)

    if "Extract" in tab_map:
        with tab_map["Extract"]:
            extract.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name, st.session_state.bookmarks_data)
            
    if "Dividir" in tab_map:
        with tab_map["Dividir"]:
            split.render(doc_cached, st.session_state.pdf_name, st.session_state.bookmarks_data)
            
    if "Otimizar" in tab_map:
        with tab_map["Otimizar"]:
            optimize.render(doc_cached, st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
