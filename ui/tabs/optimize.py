import streamlit as st
import fitz
import os
from ui.components import render_download_button

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🚀 Otimizar PDF")
    
    profile = st.selectbox("Perfil", ("Leve", "Recomendada", "Máxima"), index=1)
    pwd = st.text_input("Senha (opcional)", type="password", key="pass_opt")
    
    c1, c2 = st.columns(2)
    rm_meta = c1.checkbox("Remover metadados", True)
    rm_ann = c2.checkbox("Remover anotações", False)

    if st.button("Otimizar Agora", type="primary"):
        try:
            with st.spinner("Otimizando..."):
                opt = {}
                if profile == "Leve":
                    opt.update(garbage=2, deflate=True)
                elif profile == "Recomendada":
                    opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
                else:
                    opt.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, linear=True, clean=True)

                # Abre novo doc a partir dos bytes originais para não afetar o cached
                doc = fitz.open(stream=pdf_bytes_original, filetype="pdf")
                
                if rm_meta:
                    doc.set_metadata({})
                
                if rm_ann:
                    for pg in doc:
                        ann = pg.first_annot
                        while ann:
                            nxt = ann.next
                            pg.delete_annot(ann)
                            ann = nxt
                
                # Senha e permissions seria add em opt se usarmos tobytes(**opt)
                # O core/pdf_ops tem optimize_pdf que centraliza isso, poderiamos usar ele.
                # Mas aqui tem logica especifica de profile.
                
                # Se tiver senha
                if pwd:
                    # Import dinâmico ou hardcoded values se fitz nao estiver disponivel
                    from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
                    opt.update({
                        "encryption": ENCRYPT_AES_256,
                        "user_pw": pwd, "owner_pw": pwd,
                        "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE
                    })

                out_bytes = doc.tobytes(**opt)
                doc.close()

                base_name = os.path.splitext(pdf_name)[0]
                render_download_button(out_bytes, f"{base_name}_otimizado.pdf", "Baixar PDF Otimizado")
                
        except Exception as e:
            st.error(f"Erro na otimização: {e}")
