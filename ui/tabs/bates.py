import streamlit as st
import fitz
from core.bates import apply_bates_stamping
from ui.components import render_download_button
import os

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🔢 Numeração de Folhas (Bates)")
    st.info("Adicione numeração sequencial ou carimbos automáticos (ex: 'Fls. 1', 'Doc. 01').")
    
    col1, col2 = st.columns(2)
    
    with col1:
        prefix = st.text_input("Prefixo", value="Doc. 01 - Fls. ")
        suffix = st.text_input("Sufixo", value="")
        start_num = st.number_input("Começar em", min_value=1, value=1)
        
    with col2:
        pos_map = {
            "Topo Esquerda": "top_left", "Topo Centro": "top_center", "Topo Direita": "top_right",
            "Rodapé Esquerda": "bottom_left", "Rodapé Centro": "bottom_center", "Rodapé Direita": "bottom_right"
        }
        pos_label = st.selectbox("Posição", list(pos_map.keys()), index=5)
        position = pos_map[pos_label]
        
        font_size = st.slider("Tamanho da Fonte", 8, 24, 12)
        
    st.markdown("### Prévia do texto:")
    st.code(f"{prefix}{start_num}{suffix}", language="text")

    if st.button("Aplicar Numeração", type="primary"):
        try:
            with st.spinner("Carimbando páginas..."):
                # Monta pattern para o core
                # O core espera "{page_idx}", mas aqui simplificamos para o usuário
                # Vamos passar um pattern que usa o contador interno do core
                pattern = f"{prefix}{{page_idx}}{suffix}"
                
                new_bytes = apply_bates_stamping(
                    pdf_bytes_original,
                    text_pattern=pattern,
                    start_page_idx=start_num,
                    position=position,
                    font_size=font_size
                )
                
                base_name = os.path.splitext(pdf_name)[0]
                render_download_button(new_bytes, f"{base_name}_numerado.pdf", "⬇️ Baixar PDF Numerado")
                
        except Exception as e:
            st.error(f"Erro ao numerar: {e}")
