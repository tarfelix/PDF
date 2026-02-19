import streamlit as st
import fitz
import io
import zipfile
import os
from ui.components import render_download_button
from core.pdf_scanner import smart_scan
from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
from core.utils import safe_slug

def render(doc_cached: fitz.Document, pdf_name: str, bookmarks_unused=None, pdf_bytes_original: bytes = None):
    st.header("⚖️ Identificador de Peças (Smart Scan)")
    st.caption("Localiza peças jurídicas usando marcadores ou inteligência de texto (para PDFs digitalizados).")
    
    # Init state
    if "legal_found_items" not in st.session_state:
        st.session_state.legal_found_items = []
        
    # Coluna de controle
    c_scan, c_info = st.columns([1, 3])
    do_scan = c_scan.button("🔄 Escanear Documento", type="primary", help="Força uma nova varredura no documento.")
    
    if do_scan or not st.session_state.legal_found_items:
        with st.spinner("Analisando estrutura e conteúdo do PDF... Isso pode levar alguns segundos."):
            items = smart_scan(doc_cached)
            st.session_state.legal_found_items = items
            st.rerun()

    items = st.session_state.legal_found_items
    
    if not items:
        st.warning("Nenhuma peça identificada automaticamente.")
        st.info("O documento pode não ter marcadores ou texto reconhecível (OCR). Tente a aba 'Dividir' ou 'Visual' para corte manual.")
        return

    # --- Área de Seleção e Edição ---
    st.subheader(f"Encontradas {len(items)} peças possíveis")
    
    with st.expander("📝 Gerenciar e Editar Seleção", expanded=True):
        # Tools de massa
        col_tools = st.columns(4)
        if col_tools[0].button("Marcar Tudo"):
            for i in range(len(items)): st.session_state[f"sel_legal_{i}"] = True
            st.rerun()
        if col_tools[1].button("Desmarcar Tudo"):
            for i in range(len(items)): st.session_state[f"sel_legal_{i}"] = False
            st.rerun()
            
        # Lista editável
        edited_items = []
        for i, item in enumerate(items):
            # Layout de linha
            c_chk, c_name, c_start, c_end, c_source = st.columns([0.5, 3, 1, 1, 0.5])
            
            # Checkbox
            key_sel = f"sel_legal_{i}"
            if key_sel not in st.session_state:
                st.session_state[key_sel] = item.get('preselect', False)
            
            is_checked = c_chk.checkbox("##", key=key_sel, label_visibility="collapsed")
            
            # Nome (Icone + Titulo)
            icon = "🔖" if item.get('source') == 'bookmark' or item.get('source') == 'bookmark_filter' else "🔍"
            c_name.markdown(f"**{icon} {item['title']}**")
            
            # Intervalos (Editáveis)
            # Nota: Inputs numéricos no streamlit são lentos se muitos. 
            # Mas ok para < 20 peças.
            s_val = item['start_page_0_idx'] + 1
            e_val = item['end_page_0_idx'] + 1
            
            new_s = c_start.number_input("Início", 1, doc_cached.page_count, s_val, key=f"s_{i}", label_visibility="collapsed")
            new_e = c_end.number_input("Fim", new_s, doc_cached.page_count, max(e_val, new_s), key=f"e_{i}", label_visibility="collapsed")
            
            # Update item ref (cuidado com side effects)
            items[i]['start_page_0_idx'] = new_s - 1
            items[i]['end_page_0_idx'] = new_e - 1
            
            if is_checked:
                edited_items.append(items[i])
                
            # Origem
            c_source.caption(f"{item.get('source', 'unk')}")
            
    st.write(f"**{len(edited_items)}** peças selecionadas para extração.")
    
    st.divider()
    
    # Opções de Saída
    c_opts1, c_opts2 = st.columns(2)
    filename_suffix = c_opts1.text_input("Sufixo do arquivo", "_pecas")
    merge_all = c_opts2.checkbox("Mesclar tudo em um único PDF?", value=False)
    
    if st.button("🚀 Processar e Baixar", type="primary", disabled=len(edited_items)==0):
        try:
            with st.spinner("Extraindo e processando..."):
                final_files = []
                
                # Usa bytes originais para abrir o documento fonte (mais seguro)
                raw_bytes = pdf_bytes_original or st.session_state.get('pdf_doc_bytes_original')
                src_doc = fitz.open(stream=raw_bytes, filetype="pdf")
                
                for item in edited_items:
                    # Extrai intervalo
                    new_doc = fitz.open()
                    new_doc.insert_pdf(src_doc, from_page=item['start_page_0_idx'], to_page=item['end_page_0_idx'])
                    
                    # Nome
                    safe_title = safe_slug(item['title'])
                    fname = f"{safe_title}.pdf"
                    
                    final_files.append((fname, new_doc))
                    
                output_bytes = None
                out_name = "download.zip"
                mime = "application/zip"
                
                if merge_all:
                    # Merge those headers
                    merged = fitz.open()
                    for _, d in final_files:
                        merged.insert_pdf(d)
                    
                    output_bytes = merged.tobytes(garbage=4, deflate=True)
                    merged.close()
                    out_name = f"{os.path.splitext(pdf_name)[0]}{filename_suffix}.pdf"
                    mime = "application/pdf"
                else:
                    # Zip
                    zb = io.BytesIO()
                    with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
                        for fname, d in final_files:
                            # numero sequencial para ordenar
                            # ou manter original
                            b = d.tobytes(garbage=4, deflate=True)
                            zf.writestr(fname, b)
                            d.close()
                    output_bytes = zb.getvalue()
                    out_name = f"{os.path.splitext(pdf_name)[0]}{filename_suffix}.zip"
                    
                src_doc.close()
                
                render_download_button(output_bytes, out_name, "⬇️ Baixar Resultado", mime_type=mime)
                st.success("Processamento concluído!")
                
        except Exception as e:
            st.error(f"Erro no processamento: {e}")
