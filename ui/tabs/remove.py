import streamlit as st
import fitz
import os
from core.pdf_ops import remove_pages
from core.utils import parse_page_input
from ui.components import render_download_button

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str, bookmarks: list):
    st.header("🗑️ Remover por Número ou Marcador")
    to_del = set()
    
    st.subheader("Remover por Marcador")
    f1 = st.text_input("Filtrar marcadores", key="del_bm_filter")
    
    with st.container(height=200):
        for bm in bookmarks:
            if not f1 or f1.lower() in bm['display_text'].lower():
                if st.checkbox(bm['display_text'], key=f"del_{bm['id']}"):
                    to_del.update(range(bm['start_page_0_idx'], bm['end_page_0_idx'] + 1))
    
    st.subheader("Remover por Número")
    nums = st.text_input("Ex.: 1, 3-5, 10", key="del_nums")
    if nums:
        to_del.update(parse_page_input(nums, doc_cached.page_count))
    
    st.divider()
    c1, c2 = st.columns(2)
    opt = c1.checkbox("Otimizar PDF", True, key="opt_rem")
    pwd = c2.text_input("Senha (opcional)", type="password", key="pass_rem")
    
    if st.button("Executar Remoção", type="primary", disabled=not to_del):
        if len(to_del) >= doc_cached.page_count:
            st.error("Não é possível remover todas as páginas.")
        else:
            try:
                with st.spinner("Removendo..."):
                    base_name = os.path.splitext(pdf_name)[0]
                    new_bytes = remove_pages(
                        pdf_bytes_original, 
                        sorted(list(to_del)), 
                        optimize=opt, 
                        password=pwd
                    )
                    render_download_button(new_bytes, f"{base_name}_removido.pdf", "Baixar PDF Modificado")
            except Exception as e:
                st.error(f"Erro ao remover: {e}")
