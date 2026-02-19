import streamlit as st
import fitz
import os
import io
import zipfile
from ui.components import render_download_button
from core.utils import safe_slug, insert_pages
from core.pdf_scanner import find_legal_sections

# Reimportando config se precisar de ENCRYPT constantes ou definindo localmente
from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE

def render(doc_cached: fitz.Document, pdf_name: str, bookmarks: list):
    st.header("⚖️ Peças Jurídicas (por marcadores)")
    
    # Memoiza a busca de legal pieces no state se necessario, ou repassa
    if 'found_legal_pieces' not in st.session_state or not st.session_state.found_legal_pieces:
        st.session_state.found_legal_pieces = find_legal_sections(bookmarks)
        
    pcs = st.session_state.found_legal_pieces
    
    if not pcs:
        st.warning("Nenhuma peça reconhecida pelos marcadores.")
        st.info("Use 'Extrair' ou 'Visual' para selecionar páginas.")
        return

    c1, c2, c3 = st.columns(3)
    if c1.button("Selecionar todas"):   
        for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = True
        st.rerun() # Necessário para atualizar checkboxes visualmente
    if c2.button("Limpar seleção"):      
        for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = False
        st.rerun()
    if c3.button("Pré-seleção"):         
        for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = p['preselect']
        st.rerun()

    with st.container(height=320):
        for p in pcs:
            k = f"legal_piece_{p['unique_id']}"
            if k not in st.session_state: st.session_state[k] = p['preselect']
            st.checkbox(f"**{p['category']}**: {p['title']} (págs. {p['start_page_0_idx']+1}-{p['end_page_0_idx']+1})", key=k)

    st.divider()
    
    c1, c2 = st.columns(2)
    opt = c1.checkbox("Otimizar PDF", True, key="opt_legal")
    pwd = c2.text_input("Senha (opcional)", type="password", key="pass_legal")
    
    cz1, cz2 = st.columns(2)
    per_piece_zip = cz1.checkbox("Salvar cada peça separada (ZIP)", False)
    clean = cz2.checkbox("Remover metadados/anotações", False)

    if st.button("Extrair Peças Selecionadas", type="primary"):
        ranges = [(p['start_page_0_idx'], p['end_page_0_idx'], p['title'])
                  for p in pcs if st.session_state.get(f"legal_piece_{p['unique_id']}", False)]
        
        if not ranges:
            st.warning("Nenhuma peça selecionada.")
        else:
            try:
                base_name = os.path.splitext(pdf_name)[0]
                with st.spinner("Gerando saída..."):
                    if per_piece_zip:
                        zb = io.BytesIO()
                        with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for idx, (s, e, title) in enumerate(ranges, 1):
                                part = fitz.open()
                                insert_pages(part, doc_cached, list(range(s, e + 1)))
                                
                                # Aplicar limpeza e opções
                                # (Logica simplificada - idealmente movida para core se muito complexa)
                                if clean:
                                    part.set_metadata({})
                                    # clean annotations... loops pages
                                    for pg in part:
                                        ann = pg.first_annot
                                        while ann:
                                            nxt = ann.next
                                            pg.delete_annot(ann)
                                            ann = nxt
                                
                                save_opts = dict(garbage=4, deflate=True, clean=True, deflate_images=opt, deflate_fonts=opt)
                                if pwd:
                                    save_opts.update({
                                        "encryption": ENCRYPT_AES_256, 
                                        "user_pw": pwd, "owner_pw": pwd,
                                        "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE
                                    })
                                
                                part_bytes = part.tobytes(**save_opts)
                                outname = f"{base_name}_{idx:02d}_{safe_slug(title)}.pdf"
                                zf.writestr(outname, part_bytes)
                                part.close()
                                
                        render_download_button(zb.getvalue(), f"{base_name}_pecas.zip", "Baixar ZIP das Peças")
                    else:
                        new_doc = fitz.open()
                        pages = []
                        for s, e, _ in ranges:
                            pages += list(range(s, e + 1))
                        insert_pages(new_doc, doc_cached, sorted(pages))
                        
                        # Apply options like clean/pwm logic here too...
                        save_opts = dict(garbage=4, deflate=True, clean=True, deflate_images=opt, deflate_fonts=opt)
                        if clean:
                             new_doc.set_metadata({})
                        
                        out_bytes = new_doc.tobytes(**save_opts)
                        new_doc.close()
                        render_download_button(out_bytes, f"{base_name}_pecas.pdf", "Baixar Peças Unificadas")
                        
            except Exception as e:
                st.error(f"Erro ao extrair peças: {e}")
