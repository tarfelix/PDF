import streamlit as st
import fitz
import os
from core.pdf_ops import extract_pages
from core.utils import parse_page_input
from ui.components import render_download_button

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str, bookmarks: list):
    st.header("✨ Extrair por Número ou Marcador")
    to_ext = set()
    
    st.subheader("Extrair por Marcador")
    f2 = st.text_input("Filtrar marcadores", key="ext_bm_filter")
    with st.container(height=200):
        for bm in bookmarks:
            if not f2 or f2.lower() in bm['display_text'].lower():
                if st.checkbox(bm['display_text'], key=f"ext_{bm['id']}"):
                    to_ext.update(range(bm['start_page_0_idx'], bm['end_page_0_idx'] + 1))
    
    st.subheader("Extrair por Número")
    nums = st.text_input("Ex.: 1, 3-5, 10", key="ext_nums")
    if nums:
        to_ext.update(parse_page_input(nums, doc_cached.page_count))
    
    st.divider()
    c1, c2 = st.columns(2)
    opt = c1.checkbox("Otimizar PDF", True, key="opt_ext")
    pwd = c2.text_input("Senha (opcional)", type="password", key="pass_ext")
    
    if st.button("Executar Extração", type="primary", disabled=not to_ext):
        try:
            with st.spinner("Extraindo..."):
                base_name = os.path.splitext(pdf_name)[0]
                new_bytes = extract_pages(
                    pdf_bytes_original,
                    sorted(list(to_ext)),
                    optimize=opt,
                    password=pwd
                )
                render_download_button(new_bytes, f"{base_name}_extraido.pdf", "Baixar PDF Extraído")
        except Exception as e:
            st.error(f"Erro ao extrair: {e}")
