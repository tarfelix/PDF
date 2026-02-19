import streamlit as st
import fitz
import os
from ui.components import render_download_button

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🚀 Otimizar e Editar Metadados")
    
    st.subheader("1. Perfil de Compressão")
    profile = st.selectbox("Nível de Otimização", ("Leve (Web)", "Recomendada (PJe/Email)", "Máxima (Arquivo)"), index=1)
    
    st.subheader("2. Metadados e Informações")
    st.info("Edite os dados abaixo para profissionalizar o documento antes do envio.")
    
    # Carrega metadados atuais do doc em cache para preencher
    current_meta = doc_cached.metadata if doc_cached.metadata else {}
    
    c_meta1, c_meta2 = st.columns(2)
    new_title = c_meta1.text_input("Título", value=current_meta.get("title", "") or "")
    new_author = c_meta2.text_input("Autor", value=current_meta.get("author", "") or "")
    
    new_subject = st.text_input("Assunto", value=current_meta.get("subject", "") or "")
    new_keywords = st.text_input("Palavras-chave", value=current_meta.get("keywords", "") or "")
    
    st.divider()
    st.subheader("3. Segurança e Limpeza")
    
    c1, c2 = st.columns(2)
    rm_meta = c1.checkbox("🧹 Remover todos os metadados (sobrescreve acima)", False, help="Remove autor, criador e todas as tags.")
    rm_ann = c2.checkbox("📝 Remover anotações/comentários", False)
    
    pwd = st.text_input("Senha para abrir (Opcional)", type="password", help="Deixe em branco para não usar senha.")

    st.divider()
    
    if st.button("Aplicar Alterações e Baixar PDF", type="primary"):
        try:
            with st.spinner("Processando..."):
                opt = {}
                # Mapeamento de perfis
                if "Leve" in profile:
                    opt.update(garbage=2, deflate=True)
                elif "Recomendada" in profile:
                    opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
                else:
                    opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, linear=True, clean=True)

                # Abre novo doc a partir dos bytes originais
                doc = fitz.open(stream=pdf_bytes_original, filetype="pdf")
                
                # Aplica Metadados
                if rm_meta:
                    doc.set_metadata({})
                else:
                    # Preserva o que não foi editado mudando apenas os campos visíveis ou mantendo dict
                    # fitz.Document.set_metadata aceita um dict. Chaves não presentes são mantidas?
                    # A doc diz: "Changes the metadata of the document. ... Keys with None values are deleted."
                    # Vamos atualizar o metadata existente.
                    
                    new_meta = doc.metadata.copy()
                    new_meta["title"] = new_title
                    new_meta["author"] = new_author
                    new_meta["subject"] = new_subject
                    new_meta["keywords"] = new_keywords
                    # Força creator/producer se quiser limpar rastros de software antigo?
                    # new_meta["creator"] = "PDF Editor v3"
                    
                    doc.set_metadata(new_meta)
                
                # Remove Anotações
                if rm_ann:
                    for pg in doc:
                        ann = pg.first_annot
                        while ann:
                            nxt = ann.next
                            pg.delete_annot(ann)
                            ann = nxt
                
                # Configurações de Segurança
                if pwd:
                    from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
                    opt.update({
                        "encryption": ENCRYPT_AES_256,
                        "user_pw": pwd, "owner_pw": pwd,
                        "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE
                    })

                out_bytes = doc.tobytes(**opt)
                doc.close()

                base_name = os.path.splitext(pdf_name)[0]
                suffix = "_otimizado" if not rm_meta else "_limpo"
                render_download_button(out_bytes, f"{base_name}{suffix}.pdf", "⬇️ Baixar PDF Final")
                
        except Exception as e:
            st.error(f"Erro ao processar: {e}")
