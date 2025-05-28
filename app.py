import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile
from PIL import Image
import shutil # Para verificar a existência do Tesseract (se for reintroduzir OCR)

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")

# --- Título e Descrição ---
st.title("✂️ Editor e Divisor de PDF Completo")
st.markdown("""
    **Bem-vindo!** Esta aplicação permite manipular ficheiros PDF com diversas funcionalidades:
    - Mesclar múltiplos PDFs.
    - Remover páginas específicas ou baseadas em marcadores (com pesquisa).
    - Dividir PDFs grandes em partes menores.
    - Extrair um conjunto de páginas para um novo documento (com pesquisa de marcadores).
    - Gerir páginas visualmente com pré-visualizações.
    - Otimizar PDFs para tentar reduzir o tamanho do ficheiro.
""")

# --- Dicionário Padrão para o Estado da Sessão ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_merge': None, 
    'processed_pdf_bytes_optimize': None,
    'split_pdf_parts': [], 'error_message': None, 
    'last_uploaded_file_ids': [], 
    'page_previews': [], 'visual_page_selection': {}, 
    'files_to_merge': [], 
    'processing_remove': False, 'processing_split': False, 'processing_extract': False, 
    'processing_visual_delete': False, 'processing_visual_extract': False, 
    'processing_merge': False, 'processing_optimize': False,
    'active_tab_for_preview_generation': None, 'generating_previews': False,
    'current_page_count_for_inputs': 0,
    'is_single_pdf_mode': False,
    'search_term_remove_bookmarks': "", 
    'search_term_extract_bookmarks': "" 
}

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    for key, value in DEFAULT_STATE.items(): 
        if key not in st.session_state:
            st.session_state[key] = type(value)() if isinstance(value, (list, dict, set)) else value
initialize_session_state()

# --- Cache para Carregamento do PDF ---
@st.cache_resource(show_spinner="Carregando e analisando PDF...")
def load_pdf_from_bytes(pdf_bytes, filename="uploaded_pdf"):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        bookmarks = get_bookmark_ranges(doc) 
        page_count = doc.page_count
        return doc, bookmarks, page_count
    except Exception as e:
        st.error(f"Erro ao carregar o PDF '{filename}': {e}")
        return None, [], 0

# --- Funções Auxiliares ---
def get_bookmark_ranges(pdf_doc_instance):
    bookmarks_data = []
    if not pdf_doc_instance: return bookmarks_data
    try:
        toc = pdf_doc_instance.get_toc(simple=False)
    except Exception as e:
        st.error(f"Erro ao obter marcadores: {e}"); return bookmarks_data
    if not toc: return bookmarks_data
    num_total_pages_doc = pdf_doc_instance.page_count
    for i, item_i in enumerate(toc):
        if len(item_i) < 3: continue
        level_i, title_i, page_num_1_indexed_i = item_i[0], item_i[1], item_i[2]
        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc): continue
        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = num_total_pages_doc - 1
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_1_indexed_j_next = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j_next <= num_total_pages_doc): continue
            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j_next - 2; break 
        end_page_0_idx = min(max(start_page_0_idx, end_page_0_idx), num_total_pages_doc - 1)
        display_text = f"{'➡️' * level_i} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "title": title_i, 
            "start_page_0_idx": start_page_0_idx,
            "end_page_0_idx": end_page_0_idx, "level": level_i,
            "display_text": display_text, "id": f"bookmark_{i}"
        })
    return bookmarks_data

def parse_page_input(page_str, max_page_1_idx):
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
                for i_loop_parse in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i_loop_parse <= max_page_1_idx: selected_pages_0_indexed.add(i_loop_parse - 1) 
                    else: st.warning(f"Aviso: Página {i_loop_parse} (entrada direta) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
            elif part: 
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx: selected_pages_0_indexed.add(page_num_1_idx - 1) 
                else: st.warning(f"Aviso: Página {page_num_1_idx} (entrada direta) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
        except ValueError: st.warning(f"Aviso: Entrada de página inválida '{part}'. Será ignorada.")
    return sorted(list(selected_pages_0_indexed))

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn_v12"):
    for key_to_reset in DEFAULT_STATE.keys():
        st.session_state[key_to_reset] = type(DEFAULT_STATE[key_to_reset])() if isinstance(DEFAULT_STATE[key_to_reset], (list, dict, set)) else DEFAULT_STATE[key_to_reset]
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or k.startswith("extract_bookmark_") or "_input" in k or "_checkbox" in k or k.startswith("up_") or k.startswith("down_") or k.startswith("search_term_")]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    load_pdf_from_bytes.clear() 
    st.success("Estado da aplicação limpo! Por favor, carregue novos ficheiros se desejar.")
    st.rerun()

# --- Upload Único de Arquivo no Topo ---
st.header("1. Carregar Ficheiro(s) PDF")
uploaded_files = st.file_uploader(
    "Carregue um PDF para editar ou múltiplos PDFs para mesclar.",
    type="pdf",
    accept_multiple_files=True,
    key="main_pdf_uploader_v12"
)

# Lógica para lidar com os ficheiros carregados
if uploaded_files:
    current_uploaded_file_ids = sorted([f.file_id for f in uploaded_files])
    if st.session_state.last_uploaded_file_ids != current_uploaded_file_ids:
        st.session_state.last_uploaded_file_ids = current_uploaded_file_ids
        load_pdf_from_bytes.clear() 
        initialize_session_state() 
        st.session_state.last_uploaded_file_ids = current_uploaded_file_ids 
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            st.session_state.pdf_doc_bytes_original = uploaded_files[0].getvalue()
            st.session_state.pdf_name = uploaded_files[0].name
            st.session_state.files_to_merge = [] 
            doc_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
            if doc_data and doc_data[0]:
                _, bookmarks, page_count = doc_data
                st.success(f"PDF '{st.session_state.pdf_name}' ({page_count} páginas) carregado para edição e outras operações.")
                st.session_state.bookmarks_data = bookmarks
                st.session_state.current_page_count_for_inputs = page_count
            else:
                st.session_state.is_single_pdf_mode = False; st.session_state.pdf_doc_bytes_original = None
                st.error("Falha ao carregar o PDF para edição.")
        elif len(uploaded_files) > 1:
            st.session_state.is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files 
            st.session_state.pdf_doc_bytes_original = None; st.session_state.pdf_name = None
            st.session_state.bookmarks_data = []
            st.success(f"{len(uploaded_files)} PDFs carregados, prontos para a aba 'Mesclar PDFs'.")
        st.rerun() 
elif not uploaded_files and st.session_state.last_uploaded_file_ids: 
    initialize_session_state() 
    load_pdf_from_bytes.clear()
    st.session_state.last_uploaded_file_ids = [] 
    st.info("Nenhum PDF carregado. Por favor, carregue um ou mais ficheiros.")
    st.rerun()

# --- Mensagem Guia Inicial ---
if not st.session_state.pdf_doc_bytes_original and not st.session_state.files_to_merge:
    st.info(
        """
        **Como começar:**
        - **Para editar, dividir, extrair, gerir visualmente ou otimizar um PDF:** Carregue *UM* ficheiro PDF acima. As abas correspondentes aparecerão.
        - **Para mesclar PDFs:** Carregue *DOIS OU MAIS* ficheiros PDF acima. A funcionalidade estará disponível na aba "Mesclar PDFs".
        """
    )

# --- Definição e Exibição das Abas ---
st.header("2. Escolha uma Ação")
tab_titles_display = ["Mesclar PDFs"] 
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    tab_titles_display.extend(["Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente", "Otimizar PDF"])
tabs = st.tabs(tab_titles_display)
doc_cached = None 
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    doc_cached_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if doc_cached_data and doc_cached_data[0]:
        doc_cached, _, _ = doc_cached_data
    else:
        st.error("Erro ao aceder ao PDF principal em cache. Por favor, recarregue o ficheiro.")
        st.session_state.is_single_pdf_mode = False 

# --- ABA: MESCLAR PDFS ---
with tabs[0]: 
    # ... (Código da aba Mesclar, como na v11)
    st.subheader("Mesclar Múltiplos Ficheiros PDF")
    if not st.session_state.files_to_merge and not st.session_state.is_single_pdf_mode :
        st.info("Para mesclar, carregue dois ou mais ficheiros PDF na secção '1. Carregar Ficheiro(s) PDF' acima.")
    elif st.session_state.is_single_pdf_mode and len(st.session_state.files_to_merge) == 0 :
        st.info("Apenas um PDF foi carregado (para edição). Para mesclar, carregue múltiplos ficheiros na secção '1. Carregar Ficheiro(s) PDF' acima.")
    if st.session_state.files_to_merge:
        st.markdown("**Ficheiros carregados para mesclagem (reordene se necessário):**")
        def move_file_up(index_to_move):
            if index_to_move > 0:
                current_list = list(st.session_state.files_to_merge)
                current_list.insert(index_to_move - 1, current_list.pop(index_to_move))
                st.session_state.files_to_merge = current_list
                st.session_state.processed_pdf_bytes_merge = None 
        def move_file_down(index_to_move):
            current_list = list(st.session_state.files_to_merge)
            if index_to_move < len(current_list) - 1:
                current_list.insert(index_to_move + 1, current_list.pop(index_to_move))
                st.session_state.files_to_merge = current_list
                st.session_state.processed_pdf_bytes_merge = None
        for i_merge_list, f_obj in enumerate(st.session_state.files_to_merge):
            cols_merge_list = st.columns([0.1, 0.1, 0.8]) 
            with cols_merge_list[0]:
                if i_merge_list > 0:
                    st.button("⬆️", key=f"up_{f_obj.file_id}_{i_merge_list}_v12", on_click=move_file_up, args=(i_merge_list,), help="Mover para cima")
            with cols_merge_list[1]:
                if i_merge_list < len(st.session_state.files_to_merge) - 1:
                    st.button("⬇️", key=f"down_{f_obj.file_id}_{i_merge_list}_v12", on_click=move_file_down, args=(i_merge_list,), help="Mover para baixo")
            with cols_merge_list[2]:
                st.write(f"{i_merge_list+1}. {f_obj.name} ({round(f_obj.size / (1024*1024), 2)} MB)")
        st.markdown("---")
        optimize_merged_pdf = st.checkbox("Otimizar PDF mesclado ao salvar", value=True, key="optimize_merged_pdf_v12")
        if st.button("Mesclar PDFs na Ordem Acima", key="process_merge_button_v12", disabled=st.session_state.get('processing_merge', False) or len(st.session_state.files_to_merge) < 1):
            if not st.session_state.files_to_merge:
                st.warning("Por favor, carregue pelo menos um ficheiro PDF para processar.")
            elif len(st.session_state.files_to_merge) == 1:
                 st.info("Apenas um ficheiro carregado. A 'mesclagem' resultará numa cópia deste ficheiro.")
            st.session_state.processing_merge = True
            st.session_state.processed_pdf_bytes_merge = None; st.session_state.error_message = None
            merged_doc = None; merge_progress_bar = None
            with st.spinner(f"A mesclar {len(st.session_state.files_to_merge)} ficheiro(s) PDF... Por favor, aguarde."):
                try:
                    merged_doc = fitz.open() 
                    merge_progress_bar = st.progress(0, text="Iniciando mesclagem...")
                    total_files_to_merge = len(st.session_state.files_to_merge)
                    for i_merge_proc, file_to_insert in enumerate(st.session_state.files_to_merge):
                        progress_text = f"Adicionando ficheiro {i_merge_proc+1}/{total_files_to_merge}: {file_to_insert.name}"
                        merge_progress_bar.progress(int(((i_merge_proc + 1) / total_files_to_merge) * 100), text=progress_text)
                        doc_to_insert = None
                        try:
                            doc_to_insert = fitz.open(stream=file_to_insert.getvalue(), filetype="pdf")
                            merged_doc.insert_pdf(doc_to_insert) 
                        except Exception as insert_e:
                            st.error(f"Erro ao processar o ficheiro '{file_to_insert.name}' para mesclagem: {insert_e}")
                            st.session_state.error_message = f"Falha ao processar '{file_to_insert.name}'."
                            break 
                        finally:
                            if doc_to_insert: doc_to_insert.close()
                    if not st.session_state.error_message:
                        if merge_progress_bar: merge_progress_bar.empty()
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_merged_pdf: 
                            save_options.update({"deflate_images": True, "deflate_fonts": True})
                        pdf_output_buffer = io.BytesIO()
                        merged_doc.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_merge = pdf_output_buffer.getvalue()
                        st.success(f"{len(st.session_state.files_to_merge)} ficheiro(s) PDF mesclado(s) com sucesso!")
                    else:
                         if merge_progress_bar: merge_progress_bar.empty()
                except Exception as e:
                    st.session_state.error_message = f"Erro durante a mesclagem dos PDFs: {e}"; st.error(st.session_state.error_message)
                    if merge_progress_bar and hasattr(merge_progress_bar, 'empty'): merge_progress_bar.empty()
                finally:
                    if merged_doc: merged_doc.close()
            st.session_state.processing_merge = False
            st.rerun()
        if st.session_state.processed_pdf_bytes_merge:
            download_filename_merge = "documento_mesclado.pdf"
            if st.session_state.files_to_merge:
                first_file_name = os.path.splitext(st.session_state.files_to_merge[0].name)[0]
                if len(st.session_state.files_to_merge) > 1:
                    download_filename_merge = f"{first_file_name}_e_outros_mesclado.pdf"
                else:
                    download_filename_merge = f"{first_file_name}_copia.pdf"
            st.download_button(label="Baixar PDF Mesclado", data=st.session_state.processed_pdf_bytes_merge, file_name=download_filename_merge, mime="application/pdf", key="download_merge_button_v12")

# Abas de edição (só se is_single_pdf_mode for True e doc_cached for válido)
if st.session_state.is_single_pdf_mode and doc_cached:
    tab_index_offset = 1 

    with tabs[tab_index_offset]: 
        st.header("Remover Páginas do PDF")
        with st.expander("Excluir por Marcadores", expanded=True):
            st.session_state.search_term_remove_bookmarks = st.text_input(
                "Pesquisar nos marcadores:", 
                value=st.session_state.get("search_term_remove_bookmarks", ""),
                key="search_remove_bookmarks_v12"
            ).lower()
            if st.session_state.bookmarks_data:
                filtered_bookmarks_remove = [
                    bm for bm in st.session_state.bookmarks_data 
                    if st.session_state.search_term_remove_bookmarks in bm['title'].lower()
                ] if st.session_state.search_term_remove_bookmarks else st.session_state.bookmarks_data
                if not filtered_bookmarks_remove and st.session_state.search_term_remove_bookmarks:
                    st.caption("Nenhum marcador encontrado com o termo pesquisado.")
                elif not st.session_state.bookmarks_data: # Caso não haja marcadores no PDF
                    st.info("Este PDF não contém marcadores.")
                else:
                    st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir:")
                    with st.container(height=300):
                        for bm in filtered_bookmarks_remove:
                            checkbox_key = f"delete_bookmark_{bm['id']}_tab_remove_v12"
                            if checkbox_key not in st.session_state: st.session_state[checkbox_key] = False
                            st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado neste PDF.")
        with st.expander("Excluir por Números de Página", expanded=True):
            direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove_v12")
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox_tab_remove_v12")
        if st.button("Processar Remoção de Páginas", key="process_remove_button_tab_remove_v12", disabled=st.session_state.get('processing_remove', False)):
            st.session_state.processing_remove = True
            st.session_state.processed_pdf_bytes_remove = None; st.session_state.error_message = None
            with st.spinner("A processar remoção de páginas... Por favor, aguarde."):
                doc_to_modify = None
                try:
                    doc_to_modify = fitz.open(stream=doc_cached.write(), filetype="pdf")
                    selected_bookmark_pages_to_delete = set()
                    if st.session_state.bookmarks_data:
                        for bm in st.session_state.bookmarks_data: # Itera sobre todos para pegar o estado
                            if st.session_state.get(f"delete_bookmark_{bm['id']}_tab_remove_v12", False):
                                for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                    selected_bookmark_pages_to_delete.add(page_num)
                    direct_pages_to_delete_list = parse_page_input(direct_pages_str_tab_remove, doc_to_modify.page_count)
                    all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))
                    if not all_pages_to_delete_0_indexed: st.warning("Nenhuma página selecionada para exclusão.")
                    elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                        st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."; st.error(st.session_state.error_message)
                    else:
                        doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_remove: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        pdf_output_buffer = io.BytesIO()
                        doc_to_modify.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_remove = pdf_output_buffer.getvalue()
                        st.success(f"PDF processado! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                except Exception as e: st.session_state.error_message = f"Erro ao remover páginas: {e}"; st.error(st.session_state.error_message)
                finally: 
                    if doc_to_modify: doc_to_modify.close()
            st.session_state.processing_remove = False
            st.rerun()
        if st.session_state.processed_pdf_bytes_remove:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_editado.pdf"
            st.download_button(label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button_tab_remove_v12")

    if st.session_state.is_single_pdf_mode and doc_cached and len(tabs) > tab_index_offset + 1:
        with tabs[tab_index_offset + 1]:
            # ... (Lógica da aba Dividir, como na v11)
            st.header("Dividir PDF")
            # ... (conteúdo omitido para brevidade, mas é o mesmo da v11 com chaves atualizadas se necessário)

    if st.session_state.is_single_pdf_mode and doc_cached and len(tabs) > tab_index_offset + 2:
        with tabs[tab_index_offset + 2]:
            st.header("Extrair Páginas Específicas")
            with st.expander("Extrair por Marcadores", expanded=False): 
                st.session_state.search_term_extract_bookmarks = st.text_input(
                    "Pesquisar nos marcadores:", 
                    value=st.session_state.get("search_term_extract_bookmarks", ""),
                    key="search_extract_bookmarks_v12"
                ).lower()
                if st.session_state.bookmarks_data:
                    filtered_bookmarks_extract = [
                        bm for bm in st.session_state.bookmarks_data
                        if st.session_state.search_term_extract_bookmarks in bm['title'].lower()
                    ] if st.session_state.search_term_extract_bookmarks else st.session_state.bookmarks_data
                    if not filtered_bookmarks_extract and st.session_state.search_term_extract_bookmarks:
                        st.caption("Nenhum marcador encontrado com o termo pesquisado.")
                    elif not st.session_state.bookmarks_data:
                         st.info("Este PDF não contém marcadores.")
                    else:
                        st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja extrair.")
                        with st.container(height=200): 
                            for bm in filtered_bookmarks_extract:
                                checkbox_key = f"extract_bookmark_{bm['id']}_tab_extract_v12" 
                                if checkbox_key not in st.session_state: st.session_state[checkbox_key] = False
                                st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
                else:
                    st.info("Nenhum marcador encontrado neste PDF.")
            with st.expander("Extrair por Números de Página", expanded=True):
                extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract_v12")
            optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract_v12")
            if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract_v12", disabled=st.session_state.get('processing_extract', False)):
                st.session_state.processing_extract = True
                st.session_state.processed_pdf_bytes_extract = None; st.session_state.error_message = None
                doc_original_for_extract = None; new_extracted_doc = None
                with st.spinner("A extrair páginas... Por favor, aguarde."):
                    try:
                        doc_original_for_extract = fitz.open(stream=doc_cached.write(), filetype="pdf") 
                        selected_bookmark_pages_to_extract = set()
                        if st.session_state.bookmarks_data: # Usar todos os bookmarks para obter seleções
                            for bm in st.session_state.bookmarks_data:
                                if st.session_state.get(f"extract_bookmark_{bm['id']}_tab_extract_v12", False):
                                    for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                        selected_bookmark_pages_to_extract.add(page_num)
                        direct_pages_to_extract_list = parse_page_input(extract_pages_str, doc_original_for_extract.page_count)
                        all_pages_to_extract_0_indexed = sorted(list(selected_bookmark_pages_to_extract.union(set(direct_pages_to_extract_list))))
                        if not all_pages_to_extract_0_indexed: st.warning("Nenhuma página (via marcador ou direta) especificada para extração.")
                        else:
                            new_extracted_doc = fitz.open()
                            valid_pages_to_extract = [p for p in all_pages_to_extract_0_indexed if 0 <= p < doc_original_for_extract.page_count]
                            if not valid_pages_to_extract:
                                st.warning("Nenhuma página válida selecionada para extração após verificação de intervalo.")
                            else:
                                new_extracted_doc.insert_pdf(doc_original_for_extract, selected_pages=valid_pages_to_extract) 
                                save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_pdf_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                                pdf_output_buffer = io.BytesIO()
                                new_extracted_doc.save(pdf_output_buffer, **save_options); pdf_output_buffer.seek(0)
                                st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                                st.success(f"PDF com {len(valid_pages_to_extract)} página(s) extraída(s) pronto!")
                    except Exception as e: st.session_state.error_message = f"Erro ao extrair páginas: {e}"; st.error(st.session_state.error_message)
                    finally: 
                        if doc_original_for_extract: doc_original_for_extract.close()
                        if new_extracted_doc: new_extracted_doc.close()
                st.session_state.processing_extract = False
                st.rerun()
            if st.session_state.processed_pdf_bytes_extract:
                download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
                st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract_v12")

    if st.session_state.is_single_pdf_mode and doc_cached and len(tabs) > tab_index_offset + 3:
        with tabs[tab_index_offset + 3]:
            # ... (Lógica da aba Visual, como na v11)
            st.header("Gerir Páginas Visualmente")
            # ... (conteúdo omitido para brevidade)

    if st.session_state.is_single_pdf_mode and doc_cached and len(tabs) > tab_index_offset + 4:
        with tabs[tab_index_offset + 4]:
            # ... (Lógica da aba Otimizar, como na v11)
            st.header("Otimizar PDF")
            # ... (conteúdo omitido para brevidade)

# Exibir mensagem de erro global
if st.session_state.error_message and not any([st.session_state.processed_pdf_bytes_remove, 
                                                st.session_state.processed_pdf_bytes_extract, 
                                                st.session_state.processed_pdf_bytes_visual,
                                                st.session_state.processed_pdf_bytes_merge,
                                                st.session_state.processed_pdf_bytes_optimize,
                                                st.session_state.split_pdf_parts]):
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite mesclar, remover, dividir, extrair, gerir visualmente e otimizar páginas de arquivos PDF. "
    "Desenvolvido com Streamlit e PyMuPDF."
)

