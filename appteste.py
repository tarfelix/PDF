import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
from PIL import Image
import os # Para os.path.splitext

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")

# --- Título e Descrição ---
st.title("✂️ Editor e Divisor de PDF Completo")
st.markdown("""
    **Funcionalidades Principais:**
    - **Mesclar PDFs:** Combine múltiplos ficheiros PDF num único documento.
    - **Remover Páginas:** Exclua páginas específicas ou baseadas em marcadores.
    - **Dividir PDF:** Por tamanho máximo de arquivo ou a cada N páginas.
    - **Extrair Páginas:** Crie um novo PDF com um conjunto de páginas selecionadas.
    - **Extrair Peças Jurídicas (Novo!):** Identifique e extraia peças processuais (sentenças, petições, etc.) baseadas nos marcadores do PDF.
    - **Gerir Páginas Visualmente:** Pré-visualize e selecione páginas para diversas ações.
    - **Otimizar PDF:** Reduza o tamanho do ficheiro com perfis de otimização.
    
    **Bem-vindo!** Esta aplicação permite manipular ficheiros PDF de forma completa e intuitiva. 
    Carregue um ou mais arquivos para começar.
""")


# --- Dicionário Padrão para o Estado da Sessão ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 'processed_pdf_bytes_legal': None,
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_merge': None,
    'processed_pdf_bytes_optimize': None,
    'split_pdf_parts': [], 'error_message': None,
    'last_uploaded_file_ids': [],
    'page_previews': [], 'visual_page_selection': {},
    'files_to_merge': [],
    'processing_remove': False, 'processing_split': False, 'processing_extract': False, 'processing_legal_extract': False,
    'processing_visual_delete': False, 'processing_visual_extract': False,
    'processing_merge': False, 'processing_optimize': False,
    'active_tab_visual_preview_ready': False,
    'generating_previews': False,
    'current_page_count_for_inputs': 0,
    'is_single_pdf_mode': False,
    'visual_action_type': None,
    'bookmark_search_term_remove': "",
    'bookmark_search_term_extract': "",
    'found_legal_pieces': [], 
}

# --- PALAVRAS-CHAVE PARA O MÓDULO JURÍDICO ---
LEGAL_KEYWORDS = {
    "Petição Inicial": ['petição inicial', 'inicial'],
    "Defesa/Contestação": ['defesa', 'contestação'],
    "Réplica": ['réplica', 'impugnação à contestação'],
    "Sentença": ['sentença'],
    "Acórdão": ['acórdão'],
    "Decisão": ['decisão', 'decisão interlocutória'],
    "Despacho": ['despacho'],
    "Manifestação": ['manifestação', 'petição'],
    "Ata de Audiência": ['ata de audiência', 'termo de audiência'],
    "Laudo": ['laudo'],
    "Documento": ['documento'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'sumário'],
}


# --- Funções Auxiliares ---
def initialize_session_state():
    dynamic_keys_to_remove = [k for k in st.session_state if k.startswith(("delete_bookmark_", "extract_bookmark_", "select_page_preview_", "legal_piece_")) or "_input" in k or "_checkbox" in k or k.startswith(("up_", "down_"))]
    for key_to_del in dynamic_keys_to_remove:
        if key_to_del in st.session_state:
            del st.session_state[key_to_del]

    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value
        elif isinstance(value, (list, dict, set)):
             st.session_state[key] = type(value)()
        else:
             st.session_state[key] = value


def reset_specific_processing_states():
    st.session_state.processed_pdf_bytes_remove = None
    st.session_state.processed_pdf_bytes_extract = None
    st.session_state.processed_pdf_bytes_legal = None
    st.session_state.processed_pdf_bytes_visual = None
    st.session_state.processed_pdf_bytes_merge = None
    st.session_state.processed_pdf_bytes_optimize = None
    st.session_state.split_pdf_parts = []
    st.session_state.page_previews = []
    st.session_state.visual_page_selection = {}
    st.session_state.active_tab_visual_preview_ready = False
    st.session_state.error_message = None


if not hasattr(st.session_state, 'initialized_once'):
    initialize_session_state()
    st.session_state.initialized_once = True


@st.cache_data(max_entries=5)
def get_pdf_metadata(pdf_bytes, filename_for_error_reporting="pdf_file"):
    if not pdf_bytes:
        return [], 0, "Erro: Nenhum byte de PDF fornecido para metadados."
    doc_for_metadata = None
    try:
        doc_for_metadata = fitz.open(stream=pdf_bytes, filetype="pdf")
        bookmarks_data_loaded = get_bookmark_ranges(doc_for_metadata)
        num_pages = doc_for_metadata.page_count
        return bookmarks_data_loaded, num_pages, None
    except fitz.EmptyFileError:
        return [], 0, f"Erro ao carregar metadados do PDF ({filename_for_error_reporting}): Arquivo vazio ou não é um PDF válido."
    except fitz.FileDataError:
        return [], 0, f"Erro ao carregar metadados do PDF ({filename_for_error_reporting}): Dados do arquivo corrompidos."
    except Exception as e:
        return [], 0, f"Erro inesperado ao carregar metadados do PDF ({filename_for_error_reporting}): {e}"
    finally:
        if doc_for_metadata:
            doc_for_metadata.close()


def get_bookmark_ranges(pdf_doc_instance):
    bookmarks_data = []
    if not pdf_doc_instance: return bookmarks_data
    toc = pdf_doc_instance.get_toc(simple=False)
    if not toc:
        return bookmarks_data
    num_total_pages_doc = pdf_doc_instance.page_count

    for i, item_i in enumerate(toc):
        if len(item_i) < 3: continue
        level_i, title_i, page_num_1_indexed_i = item_i[0], item_i[1], item_i[2]
        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc): continue

        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = start_page_0_idx
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_1_indexed_j_next = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j_next <= num_total_pages_doc): continue
            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j_next - 2
                break
        else:
            end_page_0_idx = num_total_pages_doc - 1
        end_page_0_idx = min(max(start_page_0_idx, end_page_0_idx), num_total_pages_doc - 1)
        display_text = f"{'➡️' * (level_i -1)}{'↪️' if level_i > 1 else ''} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "id": f"bm_{i}_{page_num_1_indexed_i}",
            "level": level_i, "title": title_i,
            "start_page_0_idx": start_page_0_idx, "end_page_0_idx": end_page_0_idx,
            "display_text": display_text
        })
    return bookmarks_data


def find_legal_sections_by_bookmark(bookmarks_data):
    found_pieces = []
    if not bookmarks_data:
        return found_pieces
    
    for i, bookmark in enumerate(bookmarks_data):
        bookmark_title_lower = bookmark['title'].lower()
        
        # CORREÇÃO: Flag para garantir que um marcador seja categorizado apenas uma vez.
        match_found = False
        for category, keywords in LEGAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in bookmark_title_lower:
                    piece_info = bookmark.copy()
                    piece_info['category'] = category
                    # O unique_id já era único, o problema era a duplicação na lista.
                    piece_info['unique_id'] = f"legal_{i}_{bookmark['id']}"
                    found_pieces.append(piece_info)
                    match_found = True
                    break # Para o próximo item em LEGAL_KEYWORDS
            if match_found:
                break # Para o próximo marcador (bookmark)
    return found_pieces


def parse_page_input(page_str, max_page_1_idx):
    selected_pages_0_indexed = set()
    if not page_str: return []
    parts = page_str.split(',')
    for part in parts:
        part = part.strip()
        if not part: continue
        try:
            if '-' in part:
                start_str, end_str = part.split('-')
                start_1_idx, end_1_idx = int(start_str.strip()), int(end_str.strip())
                if start_1_idx > end_1_idx: start_1_idx, end_1_idx = end_1_idx, start_1_idx
                for i_loop_parse in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i_loop_parse <= max_page_1_idx:
                        selected_pages_0_indexed.add(i_loop_parse - 1)
                    else:
                        st.warning(f"Aviso: Página {i_loop_parse} está fora do intervalo (1-{max_page_1_idx}).")
            else:
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx:
                    selected_pages_0_indexed.add(page_num_1_idx - 1)
                else:
                    st.warning(f"Aviso: Página {page_num_1_idx} está fora do intervalo (1-{max_page_1_idx}).")
        except ValueError:
            st.warning(f"Aviso: Entrada '{part}' não é válida.")
    return sorted(list(selected_pages_0_indexed))


if st.sidebar.button("Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn"):
    for key_to_reset, default_value in DEFAULT_STATE.items():
        st.session_state[key_to_reset] = type(default_value)() if isinstance(default_value, (list, dict, set)) else default_value
    dynamic_keys = [k for k in st.session_state if k.startswith(("delete_bookmark_", "extract_bookmark_", "select_page_preview_", "legal_piece_")) or "_input" in k or "_checkbox" in k or k.startswith(("up_", "down_"))]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    get_pdf_metadata.clear()
    st.session_state.initialized_once = False
    st.success("Estado da aplicação limpo! Por favor, carregue novos ficheiros se desejar.")
    st.rerun()

st.header("1. Carregar Ficheiro(s) PDF")
uploaded_files = st.file_uploader("Carregue um PDF para editar ou múltiplos PDFs para mesclar.", type="pdf", accept_multiple_files=True, key="main_pdf_uploader")
doc_cached = None 

if uploaded_files:
    current_uploaded_file_ids = sorted([f.file_id for f in uploaded_files])
    if st.session_state.last_uploaded_file_ids != current_uploaded_file_ids:
        initialize_session_state()
        get_pdf_metadata.clear()
        reset_specific_processing_states()
        st.session_state.last_uploaded_file_ids = current_uploaded_file_ids
        st.session_state.files_to_merge = []
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            st.session_state.pdf_doc_bytes_original = uploaded_files[0].getvalue()
            st.session_state.pdf_name = uploaded_files[0].name
            bookmarks, num_pages, error_msg_meta = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
            if error_msg_meta:
                st.session_state.error_message = error_msg_meta
                st.session_state.is_single_pdf_mode = False
            else:
                st.session_state.bookmarks_data = bookmarks
                st.session_state.current_page_count_for_inputs = num_pages
                st.session_state.found_legal_pieces = find_legal_sections_by_bookmark(bookmarks)
        elif len(uploaded_files) > 1:
            st.session_state.is_single_pdf_mode = False
            st.session_state.pdf_doc_bytes_original = None
            st.session_state.pdf_name = None
            st.session_state.bookmarks_data = []
            st.session_state.current_page_count_for_inputs = 0
            st.session_state.files_to_merge = uploaded_files
            st.success(f"{len(uploaded_files)} PDFs carregados para mesclagem.")
        st.rerun()
elif not uploaded_files and st.session_state.last_uploaded_file_ids:
    initialize_session_state()
    get_pdf_metadata.clear()
    reset_specific_processing_states()
    st.session_state.last_uploaded_file_ids = []
    doc_cached = None 
    st.info("Nenhum PDF carregado. Por favor, carregue um ou mais ficheiros.")
    st.rerun()

if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    if doc_cached is None: 
        try:
            doc_cached = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
            if not st.session_state.bookmarks_data or st.session_state.current_page_count_for_inputs != doc_cached.page_count:
                 bookmarks_reload, num_pages_reload, error_msg_meta_reload = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
                 if error_msg_meta_reload:
                     st.session_state.error_message = error_msg_meta_reload
                     st.session_state.is_single_pdf_mode = False
                     if doc_cached: doc_cached.close()
                     doc_cached = None 
                 else:
                    st.session_state.bookmarks_data = bookmarks_reload
                    st.session_state.current_page_count_for_inputs = num_pages_reload
                    st.session_state.found_legal_pieces = find_legal_sections_by_bookmark(bookmarks_reload)
                    if doc_cached and doc_cached.page_count != num_pages_reload:
                        st.session_state.error_message = "Inconsistência na contagem de páginas. Tente recarregar o arquivo."
                        if doc_cached: doc_cached.close()
                        doc_cached = None
                        st.session_state.is_single_pdf_mode = False
        except Exception as e_doc_open:
            st.session_state.error_message = f"Erro crítico ao abrir o PDF: {e_doc_open}"
            st.session_state.is_single_pdf_mode = False
            if doc_cached: doc_cached.close()
            doc_cached = None
elif not st.session_state.is_single_pdf_mode: 
    if doc_cached: doc_cached.close()
    doc_cached = None

st.header("2. Escolha uma Ação")
tab_titles_display = ["Mesclar PDFs"]
if st.session_state.is_single_pdf_mode and doc_cached: 
    tab_titles_display.extend(["Remover Páginas", "Dividir PDF", "Extrair Páginas", "Extrair Peças Jurídicas", "Gerir Páginas Visualmente", "Otimizar PDF"])
tabs = st.tabs(tab_titles_display)

with tabs[0]: # ABA: MESCLAR PDFS
    st.subheader("Mesclar Múltiplos Ficheiros PDF")
    if not st.session_state.files_to_merge and not st.session_state.is_single_pdf_mode:
        st.info("Para mesclar, carregue dois ou mais ficheiros PDF na secção '1. Carregar Ficheiro(s) PDF' acima.")
    elif st.session_state.is_single_pdf_mode:
        st.info("Apenas um PDF foi carregado. Para mesclar, carregue múltiplos ficheiros.")
    if st.session_state.files_to_merge:
        st.markdown("**Ficheiros carregados para mesclagem (reordene se necessário):**")
        def move_file_up_merge(index_to_move):
            st.session_state.files_to_merge.insert(index_to_move - 1, st.session_state.files_to_merge.pop(index_to_move))
            st.session_state.processed_pdf_bytes_merge = None 
        def move_file_down_merge(index_to_move):
            st.session_state.files_to_merge.insert(index_to_move + 1, st.session_state.files_to_merge.pop(index_to_move))
            st.session_state.processed_pdf_bytes_merge = None
        for i_merge_list, f_obj in enumerate(st.session_state.files_to_merge):
            cols_merge_list = st.columns([0.1, 0.1, 0.8])
            # CORREÇÃO: Chaves dos botões de reordenar precisam ser únicas
            if i_merge_list > 0: cols_merge_list[0].button("⬆️", key=f"up_{f_obj.file_id}_{i_merge_list}", on_click=move_file_up_merge, args=(i_merge_list,), help="Mover para cima")
            if i_merge_list < len(st.session_state.files_to_merge) - 1: cols_merge_list[1].button("⬇️", key=f"down_{f_obj.file_id}_{i_merge_list}", on_click=move_file_down_merge, args=(i_merge_list,), help="Mover para baixo")
            cols_merge_list[2].write(f"{i_merge_list+1}. {f_obj.name} ({round(f_obj.size / (1024*1024), 2)} MB)")
        st.markdown("---")
        optimize_merged_pdf = st.checkbox("Otimizar PDF mesclado ao salvar", value=True, key="optimize_merged_pdf")
        if st.button("Mesclar PDFs na Ordem Acima", key="process_merge_button", disabled=st.session_state.get('processing_merge', False) or len(st.session_state.files_to_merge) < 1):
            if not st.session_state.files_to_merge:
                st.warning("Por favor, carregue pelo menos um ficheiro PDF para processar.")
            else:
                st.session_state.processing_merge = True
                st.session_state.processed_pdf_bytes_merge = None
                st.session_state.error_message = None
                merged_doc_obj = None
                merge_progress_bar = st.progress(0, text="Iniciando mesclagem...")
                with st.spinner(f"A mesclar {len(st.session_state.files_to_merge)} ficheiro(s) PDF..."):
                    try:
                        merged_doc_obj = fitz.open()
                        total_files_to_merge = len(st.session_state.files_to_merge)
                        for i_merge_proc, file_to_insert_uploaded_file in enumerate(st.session_state.files_to_merge):
                            progress_text = f"Adicionando ficheiro {i_merge_proc+1}/{total_files_to_merge}: {file_to_insert_uploaded_file.name}"
                            merge_progress_bar.progress(int(((i_merge_proc + 1) / total_files_to_merge) * 100), text=progress_text)
                            doc_to_insert = None
                            try:
                                doc_to_insert = fitz.open(stream=file_to_insert_uploaded_file.getvalue(), filetype="pdf")
                                merged_doc_obj.insert_pdf(doc_to_insert)
                            except Exception as e_inner_merge:
                                st.session_state.error_message = f"Erro ao processar o ficheiro '{file_to_insert_uploaded_file.name}': {e_inner_merge}"
                                break 
                            finally:
                                if doc_to_insert: doc_to_insert.close()
                        if not st.session_state.error_message: 
                            if merge_progress_bar: merge_progress_bar.empty()
                            save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_merged_pdf:
                                save_options.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            merged_doc_obj.save(pdf_output_buffer, **save_options)
                            st.session_state.processed_pdf_bytes_merge = pdf_output_buffer.getvalue()
                            st.success(f"{len(st.session_state.files_to_merge)} ficheiro(s) PDF mesclado(s) com sucesso!")
                        else:
                             if merge_progress_bar: merge_progress_bar.empty()
                    except Exception as e_merge:
                        st.session_state.error_message = f"Erro durante a mesclagem dos PDFs: {e_merge}"
                        if merge_progress_bar and hasattr(merge_progress_bar, 'empty'): merge_progress_bar.empty()
                    finally:
                        if merged_doc_obj: merged_doc_obj.close()
                        st.session_state.processing_merge = False
                st.rerun()
    if st.session_state.processed_pdf_bytes_merge:
        first_file_name = os.path.splitext(st.session_state.files_to_merge[0].name)[0] if st.session_state.files_to_merge else "mesclado"
        if len(st.session_state.files_to_merge) > 1:
            download_filename_merge = f"{first_file_name}_e_outros_mesclado.pdf"
        else:
             download_filename_merge = f"{first_file_name}_copia.pdf"
        st.download_button(label="Baixar PDF Mesclado", data=st.session_state.processed_pdf_bytes_merge, file_name=download_filename_merge, mime="application/pdf", key="download_merge_button")

tab_index_offset = 1 
if st.session_state.is_single_pdf_mode and doc_cached:
    with tabs[tab_index_offset]: # ABA: REMOVER PÁGINAS
        st.header("Remover Páginas do PDF")
        with st.expander("Excluir por Marcadores", expanded=True):
            st.session_state.bookmark_search_term_remove = st.text_input("Pesquisar em marcadores:", value=st.session_state.get('bookmark_search_term_remove', ""), key="bookmark_search_remove_input").lower()
            if st.session_state.bookmarks_data:
                st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
                with st.container(height=300):
                    for bm in st.session_state.bookmarks_data:
                        checkbox_key = f"delete_bookmark_{bm['id']}"
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = False
                        if not st.session_state.bookmark_search_term_remove or st.session_state.bookmark_search_term_remove in bm['display_text'].lower():
                            st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado neste PDF ou PDF não carregado corretamente.")
        with st.expander("Excluir por Números de Página", expanded=True):
            direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_remove")
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox")
        if st.button("Processar Remoção de Páginas", key="process_remove_button", disabled=st.session_state.get('processing_remove', False)):
            st.session_state.processing_remove = True
            st.session_state.processed_pdf_bytes_remove = None
            st.session_state.error_message = None 
            doc_to_modify = None
            with st.spinner("A processar remoção de páginas..."):
                try:
                    doc_to_modify = fitz.open(stream=doc_cached.write(), filetype="pdf") 
                    selected_bookmark_pages_to_delete = set()
                    if st.session_state.bookmarks_data:
                        for bm in st.session_state.bookmarks_data:
                            if st.session_state.get(f"delete_bookmark_{bm['id']}", False):
                                for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                    selected_bookmark_pages_to_delete.add(page_num)
                    direct_pages_to_delete_list = parse_page_input(direct_pages_str_tab_remove, doc_to_modify.page_count)
                    all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))
                    if not all_pages_to_delete_0_indexed:
                        st.warning("Nenhuma página selecionada para exclusão.")
                        st.session_state.processing_remove = False 
                        st.rerun() 
                    elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                        st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."
                    else:
                        doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_remove:
                            save_options.update({"deflate_images": True, "deflate_fonts": True})
                        pdf_output_buffer = io.BytesIO()
                        doc_to_modify.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_remove = pdf_output_buffer.getvalue()
                        st.success(f"PDF processado! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                except Exception as e_remove:
                    st.session_state.error_message = f"Erro ao remover páginas: {e_remove}"
                finally:
                    if doc_to_modify: doc_to_modify.close()
                    st.session_state.processing_remove = False 
            st.rerun()
        if st.session_state.processed_pdf_bytes_remove:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_removido.pdf"
            st.download_button(label="Baixar PDF com Páginas Removidas", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button")

    if len(tabs) > tab_index_offset + 1:
        with tabs[tab_index_offset + 1]: # ABA: DIVIDIR PDF
            st.header("Dividir PDF")
            split_method = st.radio("Método de Divisão:", ("Por Tamanho Máximo (MB)", "A Cada N Páginas"), key="split_method_radio", help="A divisão por tamanho pode ser lenta para PDFs grandes.")
            optimize_pdf_split = st.checkbox("Otimizar partes divididas", value=True, key="optimize_pdf_split_checkbox")
            if split_method == "Por Tamanho Máximo (MB)":
                max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=2.0, step=0.1, format="%.1f", key="max_size_mb_input")
                if st.button("Dividir por Tamanho", key="split_by_size_button", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = []
                    st.session_state.error_message = None
                    target_size_bytes = max_size_mb * 1024 * 1024
                    total_pages_original = doc_cached.page_count
                    current_part_start_page_idx = 0
                    part_number_size = 1 
                    progress_bar_split_size = st.progress(0, text="Iniciando divisão por tamanho...")
                    original_pdf_bytes_for_splitting = doc_cached.write() 
                    with st.spinner(f"Dividindo PDF por tamanho (máx. {max_size_mb} MB)..."):
                        try:
                            while current_part_start_page_idx < total_pages_original:
                                progress_bar_split_size.progress(int((current_part_start_page_idx / total_pages_original) * 100) if total_pages_original > 0 else 0, text=f"Processando parte {part_number_size}...")
                                num_pages_in_current_part = 0
                                for page_offset in range(total_pages_original - current_part_start_page_idx):
                                    pages_to_test_count = page_offset + 1
                                    end_page_to_test_idx = current_part_start_page_idx + pages_to_test_count - 1
                                    temp_doc_for_size_check = fitz.open() 
                                    temp_doc_for_size_check.insert_pdf(fitz.open(stream=original_pdf_bytes_for_splitting, filetype="pdf"), from_page=current_part_start_page_idx, to_page=end_page_to_test_idx)
                                    temp_buffer = io.BytesIO()
                                    temp_doc_for_size_check.save(temp_buffer, garbage=0, deflate=False, clean=False)
                                    current_size_bytes = len(temp_buffer.getvalue())
                                    temp_doc_for_size_check.close()
                                    if current_size_bytes <= target_size_bytes:
                                        num_pages_in_current_part = pages_to_test_count
                                    else:
                                        if num_pages_in_current_part == 0: num_pages_in_current_part = 1 
                                        break 
                                if num_pages_in_current_part == 0 and current_part_start_page_idx < total_pages_original:
                                    num_pages_in_current_part = total_pages_original - current_part_start_page_idx
                                    if num_pages_in_current_part <=0: break
                                if num_pages_in_current_part > 0:
                                    final_part_doc = fitz.open()
                                    final_part_doc.insert_pdf(fitz.open(stream=original_pdf_bytes_for_splitting, filetype="pdf"), from_page=current_part_start_page_idx, to_page=current_part_start_page_idx + num_pages_in_current_part - 1)
                                    part_buffer_final = io.BytesIO()
                                    save_options_split_size = {"garbage": 3, "deflate": True, "clean": True}
                                    if optimize_pdf_split: save_options_split_size.update({"deflate_images": True, "deflate_fonts": True, "garbage": 4})
                                    final_part_doc.save(part_buffer_final, **save_options_split_size)
                                    final_part_doc.close()
                                    part_name_size = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parte{part_number_size}_tam.pdf"
                                    st.session_state.split_pdf_parts.append({"name": part_name_size, "data": part_buffer_final.getvalue()})
                                    current_part_start_page_idx += num_pages_in_current_part
                                    part_number_size += 1
                                else: break
                            if progress_bar_split_size: progress_bar_split_size.empty()
                            if not st.session_state.split_pdf_parts and total_pages_original > 0:
                                 st.warning("Não foi possível dividir o PDF com os critérios de tamanho fornecidos.")
                            elif st.session_state.split_pdf_parts:
                                 st.success(f"{len(st.session_state.split_pdf_parts)} partes criadas com sucesso!")
                        except Exception as e_split_size:
                            st.session_state.error_message = f"Erro ao dividir por tamanho: {e_split_size}"
                            if progress_bar_split_size: progress_bar_split_size.empty()
                        finally:
                            st.session_state.processing_split = False
                    st.rerun()
            elif split_method == "A Cada N Páginas":
                pages_per_split_val = st.number_input("Número de páginas por parte:", min_value=1, value=max(1, st.session_state.current_page_count_for_inputs // 10 if st.session_state.current_page_count_for_inputs > 0 else 10), step=1, key="pages_per_split_input")
                if st.button("Dividir por Número de Páginas", key="split_by_count_button", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = []
                    st.session_state.error_message = None
                    progress_bar_split_count = st.progress(0, text="Iniciando divisão por contagem...")
                    original_doc_for_split_count_bytes = doc_cached.write() 
                    with st.spinner(f"Dividindo PDF a cada {pages_per_split_val} páginas..."):
                        temp_doc_reader = None
                        try:
                            temp_doc_reader = fitz.open(stream=original_doc_for_split_count_bytes, filetype="pdf")
                            total_pages_original = temp_doc_reader.page_count
                            part_number_count = 1 
                            num_parts_expected = (total_pages_original + pages_per_split_val - 1) // pages_per_split_val if pages_per_split_val > 0 else 0
                            for i_split_count in range(0, total_pages_original, pages_per_split_val):
                                progress_text_val = f"Criando parte {part_number_count}/{num_parts_expected}..."
                                progress_value = int((part_number_count / num_parts_expected) * 100) if num_parts_expected > 0 else 0
                                progress_bar_split_count.progress(progress_value, text=progress_text_val)
                                new_part_doc = fitz.open() 
                                new_part_doc.insert_pdf(temp_doc_reader, from_page=i_split_count, to_page=min(i_split_count + pages_per_split_val - 1, total_pages_original - 1))
                                part_buffer = io.BytesIO()
                                save_options_split_count = {"garbage": 3, "deflate": True, "clean": True} 
                                if optimize_pdf_split: save_options_split_count.update({"deflate_images": True, "deflate_fonts": True, "garbage": 4})
                                new_part_doc.save(part_buffer, **save_options_split_count)
                                new_part_doc.close()
                                part_name_count = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parte{part_number_count}_pag.pdf" 
                                st.session_state.split_pdf_parts.append({"name": part_name_count, "data": part_buffer.getvalue()})
                                part_number_count += 1
                            if progress_bar_split_count: progress_bar_split_count.empty()
                            st.success(f"{len(st.session_state.split_pdf_parts)} partes criadas com sucesso!")
                        except Exception as e_split_count:
                            st.session_state.error_message = f"Erro ao dividir por número de páginas: {e_split_count}"
                            if progress_bar_split_count: progress_bar_split_count.empty()
                        finally:
                            if temp_doc_reader: temp_doc_reader.close()
                            st.session_state.processing_split = False
                    st.rerun()
            if st.session_state.split_pdf_parts:
                st.markdown("---")
                st.subheader("Ficheiros Divididos:")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for part in st.session_state.split_pdf_parts:
                        zip_file.writestr(part["name"], part["data"])
                zip_buffer.seek(0)
                st.download_button(label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP", data=zip_buffer, file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip", mime="application/zip", key="download_zip_button")
                st.markdown("---")
                for i_part_dl, part_data in enumerate(st.session_state.split_pdf_parts):
                    st.download_button(label=f"Baixar {part_data['name']}", data=part_data["data"], file_name=part_data["name"], mime="application/pdf", key=f"download_part_{i_part_dl}")

    if len(tabs) > tab_index_offset + 2:
        with tabs[tab_index_offset + 2]: # ABA: EXTRAIR PÁGINAS
            st.header("Extrair Páginas Específicas")
            with st.expander("Extrair por Marcadores", expanded=False):
                st.session_state.bookmark_search_term_extract = st.text_input("Pesquisar em marcadores:", value=st.session_state.get('bookmark_search_term_extract', ""), key="bookmark_search_extract_input").lower()
                if st.session_state.bookmarks_data:
                    st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja extrair.")
                    with st.container(height=200):
                        for bm in st.session_state.bookmarks_data:
                            checkbox_key = f"extract_bookmark_{bm['id']}"
                            if checkbox_key not in st.session_state:
                                st.session_state[checkbox_key] = False
                            if not st.session_state.bookmark_search_term_extract or st.session_state.bookmark_search_term_extract in bm['display_text'].lower():
                                st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
                else:
                    st.info("Nenhum marcador encontrado neste PDF ou PDF não carregado corretamente.")
            with st.expander("Extrair por Números de Página", expanded=True):
                extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input")
            optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox")
            if st.button("Processar Extração de Páginas", key="process_extract_button", disabled=st.session_state.get('processing_extract', False)):
                st.session_state.processing_extract = True
                st.session_state.processed_pdf_bytes_extract = None
                st.session_state.error_message = None
                new_extracted_doc = None
                with st.spinner("A processar extração de páginas..."):
                    try:
                        selected_bookmark_pages_to_extract = set()
                        if st.session_state.bookmarks_data:
                            for bm in st.session_state.bookmarks_data:
                                if st.session_state.get(f"extract_bookmark_{bm['id']}", False):
                                    for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                        selected_bookmark_pages_to_extract.add(page_num)
                        direct_pages_to_extract_list = parse_page_input(extract_pages_str, doc_cached.page_count)
                        all_pages_to_extract_0_indexed = sorted(list(selected_bookmark_pages_to_extract.union(set(direct_pages_to_extract_list))))
                        if not all_pages_to_extract_0_indexed:
                            st.warning("Nenhuma página selecionada para extração.")
                            st.session_state.processing_extract = False
                            st.rerun()
                        else:
                            new_extracted_doc = fitz.open() 
                            new_extracted_doc.insert_pdf(doc_cached, select=all_pages_to_extract_0_indexed)
                            save_options_extract = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_extract:
                                save_options_extract.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            new_extracted_doc.save(pdf_output_buffer, **save_options_extract)
                            st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                            st.success(f"PDF processado! {len(all_pages_to_extract_0_indexed)} página(s) extraída(s).")
                    except Exception as e_extract:
                        st.session_state.error_message = f"Erro ao extrair páginas: {e_extract}"
                    finally:
                        if new_extracted_doc: new_extracted_doc.close()
                        st.session_state.processing_extract = False 
                st.rerun()
            if st.session_state.processed_pdf_bytes_extract:
                download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
                st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button")

    if len(tabs) > tab_index_offset + 3:
        with tabs[tab_index_offset + 3]: # ABA: EXTRAIR PEÇAS JURÍDICAS
            st.header("Extrair Peças Jurídicas (por Marcadores)")
            st.info("Esta funcionalidade identifica peças processuais comuns baseadas nos marcadores (bookmarks) do PDF. Funciona melhor com PDFs gerados por sistemas como o PJe.")
            if not st.session_state.get('found_legal_pieces'):
                st.warning("Nenhuma peça jurídica comum foi identificada nos marcadores deste PDF. Você pode usar a aba 'Extrair Páginas' para uma extração manual.")
            else:
                st.markdown("**Peças identificadas no processo:**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Selecionar Todas as Peças", key="select_all_legal"):
                        for piece in st.session_state.found_legal_pieces:
                            st.session_state[f"legal_piece_{piece['unique_id']}"] = True
                        st.rerun()
                with col2:
                    if st.button("Limpar Seleção", key="clear_all_legal"):
                        for piece in st.session_state.found_legal_pieces:
                            st.session_state[f"legal_piece_{piece['unique_id']}"] = False
                        st.rerun()
                st.markdown("---")
                with st.container(height=400):
                    for piece in st.session_state.found_legal_pieces:
                        checkbox_key = f"legal_piece_{piece['unique_id']}"
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = False
                        label = f"**{piece['category']}**: {piece['title']} (Págs. {piece['start_page_0_idx'] + 1} a {piece['end_page_0_idx'] + 1})"
                        st.checkbox(label, value=st.session_state[checkbox_key], key=checkbox_key)
                st.markdown("---")
                optimize_legal_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_legal_extract_checkbox")
                if st.button("Extrair Peças Selecionadas", key="process_legal_extract_button", disabled=st.session_state.get('processing_legal_extract', False)):
                    selected_pages_to_extract = set()
                    for piece in st.session_state.found_legal_pieces:
                        if st.session_state.get(f"legal_piece_{piece['unique_id']}", False):
                            for page_num in range(piece["start_page_0_idx"], piece["end_page_0_idx"] + 1):
                                selected_pages_to_extract.add(page_num)
                    if not selected_pages_to_extract:
                        st.warning("Nenhuma peça foi selecionada para extração.")
                    else:
                        st.session_state.processing_legal_extract = True
                        st.session_state.processed_pdf_bytes_legal = None
                        st.session_state.error_message = None
                        new_legal_doc = None
                        with st.spinner(f"Extraindo {len(selected_pages_to_extract)} página(s)..."):
                            try:
                                sorted_pages = sorted(list(selected_pages_to_extract))
                                new_legal_doc = fitz.open()
                                new_legal_doc.insert_pdf(doc_cached, select=sorted_pages)
                                save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_legal_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                                pdf_output_buffer = io.BytesIO()
                                new_legal_doc.save(pdf_output_buffer, **save_options)
                                st.session_state.processed_pdf_bytes_legal = pdf_output_buffer.getvalue()
                                st.success("PDF com as peças selecionadas foi gerado com sucesso!")
                            except Exception as e:
                                st.session_state.error_message = f"Erro ao extrair peças jurídicas: {e}"
                            finally:
                                if new_legal_doc: new_legal_doc.close()
                                st.session_state.processing_legal_extract = False
                        st.rerun()
            if st.session_state.processed_pdf_bytes_legal:
                download_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_pecas_selecionadas.pdf"
                st.download_button(label="Baixar PDF com Peças Selecionadas", data=st.session_state.processed_pdf_bytes_legal, file_name=download_filename, mime="application/pdf", key="download_legal_extract_button")

    if len(tabs) > tab_index_offset + 4:
        with tabs[tab_index_offset + 4]: # ABA: GERIR PÁGINAS VISUALMENTE
            st.header("Gerir Páginas Visualmente")
            if not st.session_state.get('active_tab_visual_preview_ready', False) and doc_cached and not st.session_state.generating_previews:
                st.session_state.generating_previews = True
                with st.spinner("Gerando pré-visualizações das páginas..."):
                    previews = []
                    preview_progress = st.progress(0, text="Iniciando geração de previews...")
                    total_pages_for_preview = doc_cached.page_count
                    for i_prev_gen in range(total_pages_for_preview):
                        preview_progress.progress(int(((i_prev_gen + 1) / total_pages_for_preview) * 100), text=f"Gerando preview da página {i_prev_gen + 1}/{total_pages_for_preview}")
                        page_obj = doc_cached.load_page(i_prev_gen)
                        page_img = page_obj.get_pixmap(dpi=72) 
                        img_byte_arr = io.BytesIO()
                        img = Image.frombytes("RGB", [page_img.width, page_img.height], page_img.samples)
                        img.save(img_byte_arr, format='PNG')
                        previews.append(img_byte_arr.getvalue())
                    st.session_state.page_previews = previews
                    if preview_progress: preview_progress.empty()
                    st.session_state.generating_previews = False
                    st.session_state.active_tab_visual_preview_ready = True
                st.rerun()
            if not st.session_state.page_previews and doc_cached: 
                st.info("As pré-visualizações das páginas serão geradas. Se não aparecerem, recarregue ou clique novamente nesta aba.")
            elif doc_cached: 
                st.markdown(f"Total de páginas: {len(st.session_state.page_previews)}. Selecione as páginas abaixo:")
                num_cols_preview = st.sidebar.slider("Colunas para pré-visualização:", 2, 8, 4, key="preview_cols_slider")
                cols_preview_display = st.columns(num_cols_preview)
                for i_preview, img_bytes_preview in enumerate(st.session_state.page_previews):
                    with cols_preview_display[i_preview % num_cols_preview]:
                        page_key = f"select_page_preview_{i_preview}"
                        if i_preview not in st.session_state.visual_page_selection: 
                            st.session_state.visual_page_selection[i_preview] = False
                        current_selection_state = st.session_state.visual_page_selection[i_preview]
                        st.image(img_bytes_preview, width=120) 
                        new_selection_state = st.checkbox(f"Página {i_preview+1}", value=current_selection_state, key=page_key, label_visibility="collapsed")
                        if new_selection_state != current_selection_state:
                            st.session_state.visual_page_selection[i_preview] = new_selection_state
                            st.rerun() 
                selected_page_indices = sorted([idx for idx, selected in st.session_state.visual_page_selection.items() if selected])
                st.markdown(f"**Páginas selecionadas (base 0):** {selected_page_indices if selected_page_indices else 'Nenhuma'}")
                col_action1, col_action2 = st.columns(2)
                with col_action1:
                    if st.button("Excluir Páginas Selecionadas", key="delete_visual_button", disabled=st.session_state.get('processing_visual_delete', False)):
                        st.session_state.processing_visual_delete = True
                        st.session_state.processed_pdf_bytes_visual = None
                        st.session_state.error_message = None
                        st.session_state.visual_action_type = "excluido_vis"
                        if not selected_page_indices:
                            st.warning("Nenhuma página selecionada para exclusão.")
                            st.session_state.processing_visual_delete = False
                        else:
                            doc_visual_modify = None
                            try:
                                doc_visual_modify = fitz.open(stream=doc_cached.write(), filetype="pdf")
                                if len(selected_page_indices) >= doc_visual_modify.page_count:
                                    st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."
                                else:
                                    doc_visual_modify.delete_pages(selected_page_indices)
                                    save_options_visual = {"garbage": 4, "deflate": True, "clean": True} 
                                    pdf_output_buffer = io.BytesIO()
                                    doc_visual_modify.save(pdf_output_buffer, **save_options_visual)
                                    st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                    st.success(f"{len(selected_page_indices)} página(s) excluída(s) visualmente.")
                                    st.session_state.visual_page_selection = {} 
                                    st.session_state.active_tab_visual_preview_ready = False 
                            except Exception as e_vis_del:
                                st.session_state.error_message = f"Erro ao excluir páginas visualmente: {e_vis_del}"
                            finally:
                                if doc_visual_modify: doc_visual_modify.close()
                                st.session_state.processing_visual_delete = False 
                        st.rerun()
                with col_action2:
                    if st.button("Extrair Páginas Selecionadas", key="extract_visual_button", disabled=st.session_state.get('processing_visual_extract', False)):
                        st.session_state.processing_visual_extract = True
                        st.session_state.processed_pdf_bytes_visual = None
                        st.session_state.error_message = None
                        st.session_state.visual_action_type = "extraido_vis"
                        if not selected_page_indices:
                            st.warning("Nenhuma página selecionada para extração.")
                            st.session_state.processing_visual_extract = False
                        else:
                            doc_visual_extract_obj = None 
                            try:
                                doc_visual_extract_obj = fitz.open()
                                doc_visual_extract_obj.insert_pdf(doc_cached, select=selected_page_indices)
                                save_options_visual = {"garbage": 4, "deflate": True, "clean": True} 
                                pdf_output_buffer = io.BytesIO()
                                doc_visual_extract_obj.save(pdf_output_buffer, **save_options_visual)
                                st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                st.success(f"{len(selected_page_indices)} página(s) extraída(s) visualmente.")
                                st.session_state.visual_page_selection = {} 
                            except Exception as e_vis_ext:
                                st.session_state.error_message = f"Erro ao extrair páginas visualmente: {e_vis_ext}"
                            finally:
                                if doc_visual_extract_obj: doc_visual_extract_obj.close()
                                st.session_state.processing_visual_extract = False 
                        st.rerun()
                if st.session_state.processed_pdf_bytes_visual and st.session_state.visual_action_type:
                    action_type_label = st.session_state.visual_action_type.replace('_vis', '').replace('_', ' ')
                    download_filename_visual = f"{os.path.splitext(st.session_state.pdf_name)[0]}_{st.session_state.visual_action_type}.pdf"
                    st.download_button(label=f"Baixar PDF ({action_type_label})", data=st.session_state.processed_pdf_bytes_visual, file_name=download_filename_visual, mime="application/pdf", key="download_visual_button")

    if len(tabs) > tab_index_offset + 5:
        with tabs[tab_index_offset + 5]: # ABA: OTIMIZAR PDF
            st.header("Otimizar PDF")
            st.markdown("Aplique otimizações ao PDF principal carregado para tentar reduzir o seu tamanho. Os resultados podem variar.")
            optimization_profiles = {
                "Nenhuma": "Não aplica otimizações extras ao salvar.",
                "Leve": "Remove dados desnecessários e aplica compressão básica.",
                "Recomendada": "Limpeza mais profunda e compressão de imagens/fontes.",
                "Máxima Tentativa": "Usa todas as opções de compressão sem perdas."
            }
            selected_profile_name = st.selectbox("Escolha um Perfil de Otimização:", options=list(optimization_profiles.keys()), index=2, help="Selecione o nível de otimização desejado.", key="optimize_profile_select")
            st.caption(optimization_profiles[selected_profile_name])
            if st.button("Otimizar PDF e Preparar Download", key="optimize_pdf_button", disabled=st.session_state.get('processing_optimize', False)):
                st.session_state.processing_optimize = True
                st.session_state.processed_pdf_bytes_optimize = None
                st.session_state.error_message = None
                doc_to_optimize = None
                with st.spinner("A otimizar o PDF..."):
                    try:
                        doc_to_optimize = fitz.open(stream=doc_cached.write(), filetype="pdf") 
                        save_options_optimize = {"clean": True} 
                        if selected_profile_name == "Leve": save_options_optimize.update({"garbage": 2, "deflate": True})
                        elif selected_profile_name == "Recomendada": save_options_optimize.update({"garbage": 4, "deflate": True, "deflate_images": True, "deflate_fonts": True})
                        elif selected_profile_name == "Máxima Tentativa": save_options_optimize.update({"garbage": 4, "deflate": True, "deflate_images": True, "deflate_fonts": True})
                        optimized_pdf_buffer = io.BytesIO()
                        doc_to_optimize.save(optimized_pdf_buffer, **save_options_optimize)
                        st.session_state.processed_pdf_bytes_optimize = optimized_pdf_buffer.getvalue()
                        original_size_bytes = len(st.session_state.pdf_doc_bytes_original)
                        optimized_size_bytes = len(st.session_state.processed_pdf_bytes_optimize)
                        st.success(f"PDF otimizado com o perfil '{selected_profile_name}'!")
                        st.info(f"Tamanho Original: {original_size_bytes / 1024:.2f} KB | Tamanho Otimizado: {optimized_size_bytes / 1024:.2f} KB")
                        if original_size_bytes > 0 and optimized_size_bytes < original_size_bytes:
                            st.info(f"Redução de tamanho: {((original_size_bytes - optimized_size_bytes) / original_size_bytes) * 100:.2f}%")
                    except Exception as e_optimize:
                        st.session_state.error_message = f"Erro durante a otimização do PDF: {e_optimize}"
                    finally:
                        if doc_to_optimize: doc_to_optimize.close()
                        st.session_state.processing_optimize = False
                st.rerun()
            if st.session_state.processed_pdf_bytes_optimize:
                download_filename_optimize = f"{os.path.splitext(st.session_state.pdf_name)[0]}_otimizado.pdf"
                st.download_button(label="Baixar PDF Otimizado", data=st.session_state.processed_pdf_bytes_optimize, file_name=download_filename_optimize, mime="application/pdf", key="download_optimized_pdf_button")

active_processing_flags = [st.session_state.get(k, False) for k in st.session_state if k.startswith('processing_')]
show_global_error = st.session_state.error_message and not any(active_processing_flags)
if show_global_error:
    st.sidebar.error(f"Último erro: {st.session_state.error_message}")

if 'doc_cached' in globals() and doc_cached is not None and not st.session_state.is_single_pdf_mode:
    doc_cached.close()
    doc_cached = None
