# CÓDIGO AJUSTADO - PDF Streamlit App
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
    "Despacho": ['despacho'],
    "Decisão": ['decisão', 'decisão interlocutória'],
    "Sentença": ['sentença'],
    "Acórdão": ['acórdão'],
    "Manifestação": ['manifestação', 'petição'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'sumário'],
    "Documento": ['documento'],
    "Laudo": ['laudo'],
    "Ata de Audiência": ['ata de audiência', 'termo de audiência'],
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
        for category, keywords in LEGAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in bookmark_title_lower:
                    piece_info = bookmark.copy()
                    piece_info['category'] = category
                    piece_info['unique_id'] = f"legal_{i}_{bookmark['id']}"
                    found_pieces.append(piece_info)
                    break 
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
            if i_merge_list > 0: cols_merge_list[0].button("⬆️", key=f"up_{f_obj.file_id}", on_click=move_file_up_merge, args=(i_merge_list,), help="Mover para cima")
            if i_merge_list < len(st.session_state.files_to_merge) - 1: cols_merge_list[1].button("⬇️", key=f"down_{
