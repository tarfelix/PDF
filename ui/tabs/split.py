import streamlit as st
import io
import zipfile
import os
from core.pdf_ops import split_pdf_by_count, split_pdf_by_size, extract_pages
from ui.components import render_download_button
from core.utils import safe_slug, insert_pages
import fitz

def render(doc_cached: fitz.Document, pdf_name: str, bookmarks: list):
    st.header("🔪 Dividir PDF")
    mode = st.radio("Método", ("A cada N páginas", "Por tamanho (MB)", "Por marcadores"), horizontal=True)
    opt = st.checkbox("Otimizar partes", True, key="opt_split")

    base_name = os.path.splitext(pdf_name)[0]
    pdf_bytes = doc_cached.write()

    if mode == "A cada N páginas":
        n = st.number_input("N páginas por parte", 1, max(1, doc_cached.page_count), 10)
        if st.button("Dividir por Número", type="primary"):
            try:
                with st.spinner("Dividindo..."):
                    parts = split_pdf_by_count(pdf_bytes, n, optimize=opt)
                    
                    zb = io.BytesIO()
                    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for suffix, data in parts: 
                            zf.writestr(f"{base_name}{suffix}.pdf", data)
                    
                    render_download_button(zb.getvalue(), f"{base_name}_partes.zip", "Baixar ZIP")
            except Exception as e:
                st.error(f"Erro ao dividir: {e}")

    elif mode == "Por tamanho (MB)":
        max_mb = st.number_input("Tamanho por parte (MB)", 0.5, 500.0, 5.0, 0.1)
        if st.button("Dividir por Tamanho", type="primary"):
            try:
                with st.spinner("Dividindo por tamanho..."):
                    parts = split_pdf_by_size(pdf_bytes, max_mb, optimize=opt)
                    
                    zb = io.BytesIO()
                    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for suffix, data in parts:
                            zf.writestr(f"{base_name}{suffix}.pdf", data)
                    
                    render_download_button(zb.getvalue(), f"{base_name}_partes_por_tamanho.zip", "Baixar ZIP")
            except Exception as e:
                st.error(f"Erro ao dividir: {e}")

    else:  # Por marcadores
        st.write("Cria um arquivo por marcador (nível selecionado).")
        level = st.number_input("Nível do marcador", 1, 10, 1, 1)
        filt = st.text_input("Filtrar por texto (opcional)")
        
        if st.button("Dividir por Marcadores", type="primary"):
            try:
                with st.spinner("Dividindo por marcadores..."):
                    parts = []
                    for bm in bookmarks:
                        if bm.get("level", 1) != level: continue
                        if filt and filt.lower() not in bm["title"].lower(): continue

                        # Recria lógica localmente pois precisa de acesso aos bytes originais
                        # Ou usa extract_pages do core se adaptarmos para range, 
                        # mas aqui extrai um por um.
                        
                        part = fitz.open()
                        rng = list(range(bm['start_page_0_idx'], bm['end_page_0_idx'] + 1))
                        insert_pages(part, doc_cached, rng)
                        
                        # Otimização básica manual aqui ou extrair para func helper
                        save_opts = {"garbage": 3, "deflate": True, "clean": True}
                        if opt:
                             save_opts.update({"deflate_images": True, "deflate_fonts": True})
                             
                        part_bytes = part.tobytes(**save_opts)
                        part.close()
                        
                        parts.append((f"{base_name}_{safe_slug(bm['title'])}.pdf", part_bytes))

                    if not parts:
                        st.warning("Nenhum marcador encontrado.")
                    else:
                        zb = io.BytesIO()
                        with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for name, data in parts:
                                zf.writestr(name, data)
                        
                        render_download_button(zb.getvalue(), f"{base_name}_por_marcadores.zip", "Baixar ZIP")
            except Exception as e:
                 st.error(f"Erro ao dividir por marcadores: {e}")
