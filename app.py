import streamlit as st
import fitz  # PyMuPDF
import os
import io # Para trabalhar com bytes em memória
import zipfile # Para criar arquivos ZIP

# Configuração da página
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Pro")

st.title("✂️ Editor e Divisor de PDF Pro")
st.markdown("""
    **Funcionalidades:**
    1.  **Remover Páginas:** Exclua seções baseadas em marcadores (bookmarks) ou números de página específicos.
    2.  **Dividir PDF:**
        * Por tamanho máximo de arquivo.
        * A cada N páginas.
    3.  **Extrair Páginas:** Crie um novo PDF contendo apenas as páginas selecionadas.
""")

# --- Funções Auxiliares ---

def get_bookmark_ranges(pdf_doc):
    bookmarks_data = []
    if not pdf_doc:
        return bookmarks_data
    try:
        toc = pdf_doc.get_toc(simple=False)
    except Exception as e:
        st.error(f"Erro ao obter marcadores: {e}")
        return bookmarks_data
    if not toc:
        return bookmarks_data

    num_total_pages_doc = pdf_doc.page_count
    for i, item_i in enumerate(toc):
        if len(item_i) < 3:
            print(f"Aviso: Item de marcador com formato inesperado: {item_i}. Pulando.")
            continue
        level_i, title_i, page_num_1_indexed_i = item_i[0], item_i[1], item_i[2]
        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc):
            print(f"Aviso: Marcador '{title_i}' aponta para página inicial inválida ({page_num_1_indexed_i}). Pulando.")
            continue
        
        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = num_total_pages_doc - 1
        
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_1_indexed_j = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j <= num_total_pages_doc): continue
            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j - 2 
                break 
        
        end_page_0_idx = max(start_page_0_idx, end_page_0_idx)
        end_page_0_idx = min(end_page_0_idx, num_total_pages_doc - 1)
        display_text = f"{'➡️' * level_i} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "title": title_i, "start_page_0_idx": start_page_0_idx,
            "end_page_0_idx": end_page_0_idx, "level": level_i,
            "display_text": display_text, "id": f"bookmark_{i}"
        })
    return bookmarks_data

def parse_page_input_for_extraction_or_deletion(page_str, max_page_1_idx):
    """Parse a string like '1, 3-5, 8' into a sorted list of 0-indexed page numbers."""
    selected_pages_0_indexed = set()
    if not page_str.strip(): return []
    
    parts = page_str.split(',')
    for part in parts:
        part = part.strip()
        try:
            if '-' in part:
                start_str, end_str = part.split('-')
                start_1_idx, end_1_idx = int(start_str.strip()), int(end_str.strip())
                if start_1_idx > end_1_idx: start_1_idx, end_1_idx = end_1_idx, start_1_idx
                for i in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i <= max_page_1_idx: selected_pages_0_indexed.add(i - 1) 
                    else: st.warning(f"Aviso: Página {i} (entrada direta) fora do intervalo (1-{max_page_1_idx}).")
            elif part: 
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx: selected_pages_0_indexed.add(page_num_1_idx - 1) 
                else: st.warning(f"Aviso: Página {page_num_1_idx} (entrada direta) fora do intervalo (1-{max_page_1_idx}).")
        except ValueError: st.warning(f"Aviso: Entrada de página inválida '{part}'.")
    return sorted(list(selected_pages_0_indexed))

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    defaults = {
        'pdf_doc_bytes_original': None,
        'pdf_name': None,
        'bookmarks_data': [],
        'processed_pdf_bytes': None, # Para exclusão/extração de páginas
        'split_pdf_parts': [],       # Para PDFs divididos
        'error_message': None,
        'last_uploaded_filename': None,
        'clear_triggered': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar PDF Carregado e Seleções", key="clear_all"):
    st.session_state.pdf_doc_bytes_original = None
    st.session_state.pdf_name = None
    st.session_state.bookmarks_data = []
    st.session_state.processed_pdf_bytes = None
    st.session_state.split_pdf_parts = []
    st.session_state.error_message = None
    st.session_state.last_uploaded_filename = None # Para forçar recarregamento de widgets
    
    # Limpar chaves de checkboxes de marcadores e outros inputs que usam keys
    keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_") or "_input" in k or "_checkbox" in k]
    for k_del in keys_to_delete:
        if k_del in st.session_state: # Verificar se a chave ainda existe
            del st.session_state[k_del]
    st.session_state.clear_triggered = True # Sinaliza que o reset foi feito
    st.rerun() # Força o rerun para limpar a interface

if st.session_state.clear_triggered:
    st.session_state.clear_triggered = False # Reseta o gatilho


# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader_main")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        st.session_state.bookmarks_data = []
        st.session_state.processed_pdf_bytes = None
        st.session_state.split_pdf_parts = []
        st.session_state.error_message = None
        
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_")]
        for k_del in keys_to_delete:
            if k_del in st.session_state: del st.session_state[k_del]
        
        try:
            with fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf") as temp_doc:
                st.info(f"PDF '{st.session_state.pdf_name}' carregado com {temp_doc.page_count} páginas.")
                st.session_state.bookmarks_data = get_bookmark_ranges(temp_doc)
        except Exception as e:
            st.session_state.error_message = f"Erro ao abrir ou processar o PDF: {e}"
            st.error(st.session_state.error_message)
            st.session_state.pdf_doc_bytes_original = None 
else:
    if st.session_state.last_uploaded_filename is not None: # Se um arquivo foi "descarregado"
        st.session_state.pdf_doc_bytes_original = None # Limpa os bytes para desativar as abas
        st.session_state.last_uploaded_filename = None # Permite recarregar o mesmo arquivo depois


# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original:
    tab_remove, tab_split, tab_extract = st.tabs(["Remover Páginas", "Dividir PDF", "Extrair Páginas"])

    # --- ABA: REMOVER PÁGINAS ---
    with tab_remove:
        st.header("Remover Páginas do PDF")
        with st.expander("Excluir por Marcadores", expanded=False):
            if st.session_state.bookmarks_data:
                st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
                with st.container(height=300):
                    for bm in st.session_state.bookmarks_data:
                        checkbox_key = f"delete_bookmark_{bm['id']}"
                        if checkbox_key not in st.session_state: st.session_state[checkbox_key] = False
                        st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado para remoção.")

        with st.expander("Excluir por Números de Página", expanded=False):
            direct_pages_str_tab1 = st.text_input("Números das páginas (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove")
        
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar (pode afetar qualidade)", value=True, key="optimize_pdf_remove_checkbox_tab_remove")

        if st.button("Processar Remoção", key="process_remove_button_tab_remove"):
            with st.spinner("A processar remoção de páginas..."):
                st.session_state.processed_pdf_bytes = None
                st.session_state.error_message = None
                
                doc_to_modify = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                selected_bookmark_pages_to_delete = set()
                if st.session_state.bookmarks_data:
                    for bm in st.session_state.bookmarks_data:
                        if st.session_state.get(f"delete_bookmark_{bm['id']}", False):
                            for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                selected_bookmark_pages_to_delete.add(page_num)
                
                direct_pages_to_delete_list = parse_page_input_for_extraction_or_deletion(direct_pages_str_tab1, doc_to_modify.page_count)
                all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

                if not all_pages_to_delete_0_indexed:
                    st.warning("Nenhum marcador ou página foi selecionado para exclusão.")
                elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                    st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas do PDF."
                    st.error(st.session_state.error_message)
                else:
                    try:
                        doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_remove:
                            save_options["deflate_images"] = True
                            save_options["deflate_fonts"] = True
                        
                        pdf_output_buffer = io.BytesIO()
                        doc_to_modify.save(pdf_output_buffer, **save_options)
                        pdf_output_buffer.seek(0)
                        st.session_state.processed_pdf_bytes = pdf_output_buffer.getvalue()
                        st.success(f"PDF processado para remoção! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao processar o PDF para remoção: {e}"
                        st.error(st.session_state.error_message)
                    finally:
                        doc_to_modify.close()

        if st.session_state.processed_pdf_bytes:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_editado.pdf"
            st.download_button(
                label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes,
                file_name=download_filename_remove, mime="application/pdf", key="download_remove_button"
            )

    # --- ABA: DIVIDIR PDF ---
    with tab_split:
        st.header("Dividir PDF")
        
        split_method = st.radio("Método de Divisão:", ("Por Tamanho Máximo", "A Cada N Páginas"), key="split_method_radio")
        optimize_pdf_split = st.checkbox("Otimizar partes divididas (pode afetar qualidade)", value=True, key="optimize_pdf_split_checkbox_tab_split")

        if split_method == "Por Tamanho Máximo":
            max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=5.0, step=0.1, format="%.1f", key="max_size_mb_input_tab_split")
            if st.button("Dividir por Tamanho", key="split_by_size_button"):
                with st.spinner("A dividir PDF por tamanho..."):
                    st.session_state.split_pdf_parts = [] 
                    st.session_state.error_message = None
                    max_size_bytes = int(max_size_mb * 1024 * 1024)
                    try:
                        original_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                        total_pages_original = original_doc.page_count
                        current_page_index = 0
                        part_number = 1
                        while current_page_index < total_pages_original:
                            new_part_doc = fitz.open() 
                            pages_in_current_part = 0
                            while current_page_index < total_pages_original:
                                temp_doc_for_size_check = fitz.open()
                                if pages_in_current_part > 0: temp_doc_for_size_check.insert_pdf(new_part_doc)
                                temp_doc_for_size_check.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                                temp_buffer = io.BytesIO()
                                save_options_check = {"garbage": 0, "deflate": optimize_pdf_split}
                                if optimize_pdf_split: save_options_check.update({"deflate_images": True, "deflate_fonts": True})
                                temp_doc_for_size_check.save(temp_buffer, **save_options_check)
                                estimated_size = len(temp_buffer.getvalue())
                                temp_doc_for_size_check.close(); temp_buffer.close()
                                if pages_in_current_part > 0 and estimated_size > max_size_bytes: break 
                                new_part_doc.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                                current_page_index += 1; pages_in_current_part += 1
                                if estimated_size > max_size_bytes and pages_in_current_part == 1:
                                    st.warning(f"Página {current_page_index} (sozinha) excede o limite. Será uma parte separada.")
                                    break
                            if pages_in_current_part > 0:
                                part_buffer = io.BytesIO()
                                final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                                new_part_doc.save(part_buffer, **final_save_options)
                                part_buffer.seek(0)
                                part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteT{part_number}.pdf"
                                st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                                part_number += 1
                            new_part_doc.close()
                        original_doc.close()
                        if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                        else: st.warning("Não foi possível dividir o PDF.")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao dividir PDF por tamanho: {e}"; st.error(st.session_state.error_message)

        elif split_method == "A Cada N Páginas":
            pages_per_split = st.number_input("Número de páginas por parte:", min_value=1, value=10, step=1, key="pages_per_split_input")
            if st.button("Dividir por Número de Páginas", key="split_by_count_button"):
                with st.spinner("A dividir PDF por número de páginas..."):
                    st.session_state.split_pdf_parts = []
                    st.session_state.error_message = None
                    try:
                        original_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                        total_pages_original = original_doc.page_count
                        part_number = 1
                        for i in range(0, total_pages_original, pages_per_split):
                            new_part_doc = fitz.open()
                            start_page = i
                            end_page = min(i + pages_per_split - 1, total_pages_original - 1)
                            new_part_doc.insert_pdf(original_doc, from_page=start_page, to_page=end_page)
                            
                            part_buffer = io.BytesIO()
                            final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                            new_part_doc.save(part_buffer, **final_save_options)
                            part_buffer.seek(0)
                            part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteN{part_number}.pdf"
                            st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                            part_number += 1
                            new_part_doc.close()
                        original_doc.close()
                        if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                        else: st.warning("Não foi possível dividir o PDF.")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao dividir PDF por contagem: {e}"; st.error(st.session_state.error_message)

        if st.session_state.split_pdf_parts:
            st.subheader("Baixar Partes do PDF:")
            if len(st.session_state.split_pdf_parts) > 1:
                zip_buffer = io.BytesIO()
                with st.spinner("A preparar ZIP..."):
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                        for part in st.session_state.split_pdf_parts:
                            zip_file.writestr(part["name"], part["data"])
                    zip_buffer.seek(0)
                st.download_button(
                    label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP",
                    data=zip_buffer, file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip",
                    mime="application/zip", key="download_zip_button_tab_split"
                )
                st.markdown("---")
            for i, part in enumerate(st.session_state.split_pdf_parts):
                st.download_button(
                    label=f"Baixar {part['name']}", data=part["data"], file_name=part["name"],
                    mime="application/pdf", key=f"download_part_{i}_button_tab_split"
                )
    
    # --- ABA: EXTRAIR PÁGINAS ---
    with tab_extract:
        st.header("Extrair Páginas Específicas")
        extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract")
        optimize_pdf_extract = st.checkbox("Otimizar PDF extraído (pode afetar qualidade)", value=True, key="optimize_pdf_extract_checkbox_tab_extract")

        if st.button("Processar Extração", key="process_extract_button"):
            with st.spinner("A extrair páginas..."):
                st.session_state.processed_pdf_bytes = None # Reutiliza para o resultado da extração
                st.session_state.error_message = None
                
                doc_temp_extract = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                pages_to_extract_0_indexed = parse_page_input_for_extraction_or_deletion(extract_pages_str, doc_temp_extract.page_count)

                if not pages_to_extract_0_indexed:
                    st.warning("Nenhuma página foi especificada para extração.")
                else:
                    try:
                        new_extracted_doc = fitz.open() # Novo PDF para as páginas extraídas
                        # Adicionar páginas na ordem em que foram especificadas (se a ordem importar)
                        # ou manter a ordem original (mais simples: fitz.select)
                        new_extracted_doc.select(pages_to_extract_0_indexed) 
                        
                        # Se for necessário manter a ordem da string de entrada, a lógica seria mais complexa:
                        # for page_idx in pages_to_extract_0_indexed:
                        # new_extracted_doc.insert_pdf(doc_temp_extract, from_page=page_idx, to_page=page_idx)

                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_extract:
                            save_options["deflate_images"] = True
                            save_options["deflate_fonts"] = True
                        
                        pdf_output_buffer = io.BytesIO()
                        new_extracted_doc.save(pdf_output_buffer, **save_options)
                        pdf_output_buffer.seek(0)
                        st.session_state.processed_pdf_bytes = pdf_output_buffer.getvalue()
                        st.success(f"PDF com {len(pages_to_extract_0_indexed)} página(s) extraída(s) pronto para download!")
                        new_extracted_doc.close()
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao extrair páginas: {e}"
                        st.error(st.session_state.error_message)
                    finally:
                        doc_temp_extract.close()

        if st.session_state.processed_pdf_bytes and tab_extract.is_active: # Verifica se esta aba está ativa para o download
            download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
            st.download_button(
                label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes,
                file_name=download_filename_extract, mime="application/pdf", key="download_extract_button"
            )


# Exibir mensagem de erro global, se houver
if st.session_state.error_message and not st.session_state.processed_pdf_bytes and not st.session_state.split_pdf_parts:
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover, dividir e extrair páginas de arquivos PDF. "
    "Desenvolvido com Streamlit e PyMuPDF."
)
