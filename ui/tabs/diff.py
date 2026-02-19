import streamlit as st
from core.diff import compare_pdfs
import streamlit.components.v1 as components

def render():
    st.header("⚖️ Comparador de Versões (Diff)")
    st.info("Carregue dois PDFs para ver o que mudou no texto entre eles.")
    
    c1, c2 = st.columns(2)
    f1 = c1.file_uploader("Versão Original (Antiga)", type="pdf", key="diff_f1")
    f2 = c2.file_uploader("Versão Nova (Modificada)", type="pdf", key="diff_f2")
    
    if f1 and f2:
        if st.button("Comparar Textos", type="primary"):
            try:
                with st.spinner("Extraindo textos e comparando..."):
                    html = compare_pdfs(f1.getvalue(), f2.getvalue())
                    
                    st.success("Comparação concluída!")
                    
                    # Exibe HTML
                    # HtmlDiff gera um HTML completo com CSS.
                    # Vamos renderizar em um iframe ou componente html
                    st.download_button("⬇️ Baixar Relatório HTML", html, "comparacao.html", "text/html")
                    
                    st.subheader("Visualização Rápida")
                    components.html(html, height=600, scrolling=True)
                    
            except Exception as e:
                st.error(f"Erro na comparação: {e}")
