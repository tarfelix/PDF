import streamlit as st
from core.pdf_ops import images_to_pdf
from ui.components import render_download_button

def render():
    st.header("📸 Conversor de Imagens para PDF")
    st.info("Converta fotos de documentos (JPG, PNG) ou escaneamentos em um único arquivo PDF.")
    
    imgs = st.file_uploader("Selecione as imagens (ordem importa!)", type=["png", "jpg", "jpeg", "bmp", "tiff"], accept_multiple_files=True)
    
    if imgs:
        st.write(f"**{len(imgs)}** imagens selecionadas.")
        
        # Permitir reordenação simples visual? Streamlit file uploader não reordena, mas podemos listar nomes.
        # Por simplicidade v1, assume ordem de upload ou alfabética se usuário renomear.
        # st.file_uploader retorna na ordem de seleção geralmente, mas nao garantido.
        
        with st.expander("Pré-visualizar e Verificar Ordem"):
            # Mostra thumbnails em grid
            cols = st.columns(5)
            for i, img in enumerate(imgs):
                cols[i%5].image(img, caption=f"{i+1}. {img.name}", use_column_width=True)
        
        c1, c2 = st.columns(2)
        opt = c1.checkbox("Otimizar PDF final", value=True)
        name = c2.text_input("Nome do Arquivo", value="documento_digitalizado")

        if st.button("Converter para PDF", type="primary"):
            try:
                with st.spinner("Convertendo e unindo..."):
                    pdf_bytes = images_to_pdf(imgs, optimize=opt)
                    
                    if not name.lower().endswith(".pdf"): name += ".pdf"
                    render_download_button(pdf_bytes, name, "⬇️ Baixar PDF Convertido")
            except Exception as e:
                st.error(f"Erro na conversão: {e}")
