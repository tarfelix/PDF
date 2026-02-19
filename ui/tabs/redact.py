import streamlit as st
import fitz
from core.redact import redact_text_matches
from ui.components import render_download_button
import os

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🕵️ Redação e Anonimização (LGPD)")
    st.warning("Atenção: A redação remove permanentemente o texto e coloca uma tarja preta. É irreversível.")
    
    st.subheader("Redação por Palavras-Chave")
    st.info("Digite termos sensíveis (ex: CPF, nomes, valores) para cobrí-los automaticamente em todo o documento.")
    
    terms_input = st.text_area("Termos para ocultar (um por linha)", height=100)
    
    c1, c2 = st.columns(2)
    case_insensitive = c1.checkbox("Ignorar Maiúsculas/Minúsculas", True)
    
    st.markdown("##### 🤖 Redação Automática (Detectar Padrões)")
    c_auto1, c_auto2, c_auto3 = st.columns(3)
    use_cpf = c_auto1.checkbox("CPF / CNPJ")
    use_email = c_auto2.checkbox("E-mails")
    use_date = c_auto3.checkbox("Datas (DD/MM/AAAA)")
    
    if st.button("Aplicar Tarja Preta", type="primary"):
        terms = [t.strip() for t in terms_input.split('\n') if t.strip()]
        
        # Padrões selecionados
        patterns = []
        if use_cpf: patterns.extend(['cpf', 'cnpj'])
        if use_email: patterns.append('email')
        if use_date: patterns.append('date')
        
        if not terms and not patterns:
            st.error("Digite um termo ou selecione um padrão automático.")
            return

        try:
            with st.spinner("Buscando e aplicando redação..."):
                new_bytes, count = redact_text_matches(
                    pdf_bytes_original, 
                    terms, 
                    ignore_case=case_insensitive,
                    built_in_patterns=patterns
                )
                
                if count == 0:
                    st.warning("Nenhuma ocorrência encontrada para os termos informados.")
                else:
                    st.success(f"Sucesso! {count} ocorrências ocultadas.")
                    base_name = os.path.splitext(pdf_name)[0]
                    render_download_button(new_bytes, f"{base_name}_tarjado.pdf", "⬇️ Baixar PDF com Tarjas")
                    
        except Exception as e:
            st.error(f"Erro na redação: {e}")
