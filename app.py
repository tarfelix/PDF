import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
from PIL import Image
import os # Para os.path.splitext

# --- Configuração Inicial ---
# A verificação do Tesseract foi removida pois o OCR foi retirado em versões anteriores.

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")

# --- Título e Descrição ---
st.title("✂️ Editor e Divisor de PDF Completo")
st.markdown("""
    **Funcionalidades:**
    1.  **Mesclar PDFs:** Combine múltiplos ficheiros PDF num único documento, com opção de reordená-los.
    2.  **Remover Páginas:** Exclua seções com base em marcadores (bookmarks) ou números de página. (Com pesquisa em marcadores)
    3.  **Dividir PDF:** Por tamanho máximo de arquivo (MB) ou a cada N páginas.
    4.  **Extrair Páginas:** Crie um novo PDF com páginas selecionadas (via marcadores ou números diretos). (Com pesquisa em marcadores)
    5.  **Gerir Páginas Visualmente:** Pré-visualize e selecione páginas para exclusão ou extração.
    6.  **Otimizar PDF:** Reduza o tamanho do ficheiro com várias opções de otimização.
    **Bem-vindo!** Esta aplicação permite manipular ficheiros PDF com diversas funcionalidades:
    - Mesclar múltiplos PDFs.
    - Remover páginas específicas ou baseadas em marcadores.
    - Dividir PDFs grandes em partes menores.
    - Extrair um conjunto de páginas para um novo documento.
    - Gerir páginas visualmente com pré-visualizações.
    - Otimizar PDFs para tentar reduzir o tamanho do ficheiro.
""")

# --- Dicionário Padrão para o Estado da Sessão ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None,
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_merge': None,
    'processed_pdf_bytes_optimize': None, # Apenas uma vez
    'split_pdf_parts': [], 'error_message': None,
    'last_uploaded_file_ids': [],
    'page_previews': [], 'visual_page_selection': {},
    'files_to_merge': [],
    'processing_remove': False, 'processing_split': False, 'processing_extract': False,
    'processing_visual_delete': False, 'processing_visual_extract': False,
    'processing_merge': False, 'processing_optimize': False,
    'active_tab_visual_preview_ready': False, # Unificado
    'generating_previews': False,
    'current_page_count_for_inputs': 0,
    'is_single_pdf_mode': False,
    'visual_action_type': None, # Para nome do arquivo na aba visual
    'bookmark_search_term_remove': "", # Para pesquisa em marcadores na aba Remover
    'bookmark_search_term_extract': "", # Para pesquisa em marcadores na aba Extrair
}

# --- Funções Auxiliares ---
def initialize_session_state():
    """Inicializa ou reseta o estado da sessão para os valores padrão."""
    # Limpa chaves dinâmicas antes de resetar para o padrão
    dynamic_keys_to_remove = [k for k in st.session_state if k.startswith("delete_bookmark_") or \
                               k.startswith("extract_bookmark_") or "_input" in k or \
                               "_checkbox" in k or k.startswith("up_") or k.startswith("down_") or \
                               k.startswith("select_page_preview_")]
    for key_to_del in dynamic_keys_to_remove:
        if key_to_del in st.session_state:
            del st.session_state[key_to_del]

    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state: # Apenas inicializa se não existir, para não sobrescrever durante o reset do botão
            st.session_state[key] = value
        elif isinstance(value, (list, dict, set)): # Para resetar listas/dicionários no botão
             st.session_state[key] = type(value)()
        else: # Para resetar outros tipos no botão
             st.session_state[key] = value


def reset_specific_processing_states():
    """Reseta estados de processamento e outputs."""
    st.session_state.processed_pdf_bytes_remove = None
    st.session_state.processed_pdf_bytes_extract = None
    st.session_state.processed_pdf_bytes_visual = None
    st.session_state.processed_pdf_bytes_merge = None
    st.session_state.processed_pdf_bytes_optimize = None
    st.session_state.split_pdf_parts = []
    st.session_state.page_previews = []
    st.session_state.visual_page_selection = {}
    st.session_state.active_tab_visual_preview_ready = False
    st.session_state.error_message = None
    # Não resetar 'processing_flags' aqui, eles são controlados por cada aba

# Inicializa o estado da sessão na primeira execução
if not hasattr(st.session_state, 'initialized_once'):
    initialize_session_state()
    st.session_state.initialized_once = True


@st.cache_data(max_entries=2) # Cache para o documento principal e talvez um anterior
def load_pdf_from_bytes(pdf_bytes, filename="cached_pdf"):
    """Carrega um documento PDF a partir de bytes e extrai marcadores."""
    if not pdf_bytes:
        return None, [], 0
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        bookmarks_data_loaded = get_bookmark_ranges(doc)
        num_pages = doc.page_count
        # Não feche 'doc' aqui se você vai usá-lo diretamente depois (como em doc_cached)
        # O chamador deve gerenciar o ciclo de vida do 'doc' retornado
        return doc, bookmarks_data_loaded, num_pages
    except fitz.EmptyFileError:
        st.session_state.error_message = "Erro ao carregar PDF: Arquivo vazio ou não é um PDF válido."
        return None, [], 0
    except fitz.FileDataError:
        st.session_state.error_message = "Erro ao carregar PDF: Dados do arquivo corrompidos."
        return None, [], 0
    except Exception as e:
        st.session_state.error_message = f"Erro inesperado ao carregar PDF ({filename}): {e}"
        return None, [], 0

def get_bookmark_ranges(pdf_doc_instance):
    """Extrai marcadores e seus intervalos de página."""
    bookmarks_data = []
    if not pdf_doc_instance: return bookmarks_data
    toc = pdf_doc_instance.get_toc(simple=False)
    num_total_pages_doc = pdf_doc_instance.page_count

    for i, item_i in enumerate(toc):
        if len(item_i) < 3: continue # Nível, Título, Página (1-indexada)
        level_i, title_i, page_num_1_indexed_i = item_i[0], item_i[1], item_i[2]

        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc): continue # Página inválida

        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = start_page_0_idx # Padrão para bookmarks de uma página ou o último

        # Encontrar a página final do intervalo do bookmark
        # É a página antes do próximo bookmark de mesmo nível ou nível superior, ou a última página do doc
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_1_indexed_j_next = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j_next <= num_total_pages_doc): continue

            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j_next - 2 # Página anterior ao início do próximo
                break
        else: # Se o loop não deu break, este bookmark vai até o fim do documento
            end_page_0_idx = num_total_pages_doc - 1

        end_page_0_idx = min(max(start_page_0_idx, end_page_0_idx), num_total_pages_doc - 1)

        display_text = f"{'➡️' * (level_i -1)}{'↪️' if level_i > 1 else ''} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "id": f"bm_{i}_{page_num_1_indexed_i}", # ID único
            "level": level_i, "title": title_i,
            "start_page_0_idx": start_page_0_idx, "end_page_0_idx": end_page_0_idx,
            "display_text": display_text
        })
    return bookmarks_data

def parse_page_input(page_str, max_page_1_idx):
    """Converte string de entrada de páginas (ex: 1, 3-5) em lista de índices baseados em zero."""
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
                if start_1_idx > end_1_idx: start_1_idx, end_1_idx = end_1_idx, start_1_idx # Swap
                for i_loop_parse in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i_loop_parse <= max_page_1_idx:
                        selected_pages_0_indexed.add(i_loop_parse - 1)
                    else:
                        st.warning(f"Aviso: Página {i_loop_parse} (intervalo) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
            else:
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx:
                    selected_pages_0_indexed.add(page_num_1_idx - 1)
                else:
                    st.warning(f"Aviso: Página {page_num_1_idx} (entrada direta) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
        except ValueError:
            st.warning(f"Aviso: Entrada '{part}' não é um número de página ou intervalo válido. Será ignorada.")
    return sorted(list(selected_pages_0_indexed))

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn_v11_opt_ux"):
    # Reseta todas as chaves para o DEFAULT_STATE
    for key_to_reset, default_value in DEFAULT_STATE.items():
        if isinstance(default_value, (list, dict, set)):
            st.session_state[key_to_reset] = type(default_value)()
        else:
            st.session_state[key_to_reset] = default_value

    # Limpa chaves dinâmicas que não estão no DEFAULT_STATE
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or \
                    k.startswith("extract_bookmark_") or "_input" in k or \
                    k.startswith("select_page_preview_") or \
                    "_checkbox" in k or k.startswith("up_") or k.startswith("down_")]
    for k_del in dynamic_keys:
        if k_del in st.session_state:
            del st.session_state[k_del]

    load_pdf_from_bytes.clear()
    st.session_state.initialized_once = False # Força reinicialização completa no rerun
    st.success("Estado da aplicação limpo! Por favor, carregue novos ficheiros se desejar.")
    st.rerun()

# --- Upload Único de Arquivo no Topo ---
st.header("1. Carregar Ficheiro(s) PDF")
uploaded_files = st.file_uploader(
    "Carregue um PDF para editar ou múltiplos PDFs para mesclar.",
    type="pdf",
    accept_multiple_files=True,
    key="main_pdf_uploader_v11_opt_ux"
)

doc_cached = None # Para armazenar o objeto fitz.Document do PDF principal

if uploaded_files:
    current_uploaded_file_ids = sorted([f.file_id for f in uploaded_files])
    if st.session_state.last_uploaded_file_ids != current_uploaded_file_ids:
        # Arquivos mudaram, reset completo do estado relevante
        initialize_session_state() # Reseta para o padrão, incluindo chaves dinâmicas
        load_pdf_from_bytes.clear()
        reset_specific_processing_states() # Limpa outputs processados e previews
        st.session_state.last_uploaded_file_ids = current_uploaded_file_ids
        st.session_state.files_to_merge = [] # Limpa a lista de arquivos para mesclar

        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            st.session_state.pdf_doc_bytes_original = uploaded_files[0].getvalue()
            st.session_state.pdf_name = uploaded_files[0].name
            # Carrega o PDF e os bookmarks imediatamente
            doc_obj, bookmarks, num_pages = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
            if doc_obj:
                doc_cached = doc_obj # Mantém o objeto aberto para uso nas abas
                st.session_state.bookmarks_data = bookmarks
                st.session_state.current_page_count_for_inputs = num_pages
                # Não feche doc_obj aqui, ele é o doc_cached
            else:
                st.session_state.is_single_pdf_mode = False # Falha ao carregar
                st.error(f"Erro ao carregar o PDF: {st.session_state.error_message or 'Verifique o arquivo.'}")

        elif len(uploaded_files) > 1:
            st.session_state.is_single_pdf_mode = False
            st.session_state.pdf_doc_bytes_original = None
            st.session_state.pdf_name = None
            st.session_state.bookmarks_data = []
            st.session_state.current_page_count_for_inputs = 0
            st.session_state.files_to_merge = uploaded_files # Armazena os objetos UploadedFile
            st.success(f"{len(uploaded_files)} PDFs carregados para mesclagem.")
        st.rerun() # Rerun para refletir o novo estado

elif not uploaded_files and st.session_state.last_uploaded_file_ids: # Arquivos foram removidos
    initialize_session_state()
    load_pdf_from_bytes.clear()
    reset_specific_processing_states()
    st.session_state.last_uploaded_file_ids = []
    st.info("Nenhum PDF carregado. Por favor, carregue um ou mais ficheiros.")
    st.rerun()

# Recarregar doc_cached se já existir bytes e não estiver carregado (ex: após rerun sem mudança de arquivo)
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original and not doc_cached:
    doc_obj_reload, bookmarks_reload, num_pages_reload = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if doc_obj_reload:
        doc_cached = doc_obj_reload
        st.session_state.bookmarks_data = bookmarks_reload # Garante que os bookmarks estejam atualizados
        st.session_state.current_page_count_for_inputs = num_pages_reload
    else:
        st.error(f"Erro ao recarregar o PDF principal: {st.session_state.error_message or 'Tente recarregar o arquivo.'}")
        st.session_state.is_single_pdf_mode = False # Impede operações se o PDF não puder ser carregado


# --- Definição e Exibição das Abas ---
st.header("2. Escolha uma Ação")
tab_titles_display = ["Mesclar PDFs"]
if st.session_state.is_single_pdf_mode and doc_cached: # Verifica se doc_cached é válido
    tab_titles_display.extend(["Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente", "Otimizar PDF"])

tabs = st.tabs(tab_titles_display)

# --- ABA: MESCLAR PDFS ---
with tabs[0]:
    st.subheader("Mesclar Múltiplos Ficheiros PDF")
    if not st.session_state.files_to_merge and not st.session_state.is_single_pdf_mode:
        st.info("Para mesclar, carregue dois ou mais ficheiros PDF na secção '1. Carregar Ficheiro(s) PDF' acima.")
    elif st.session_state.is_single_pdf_mode:
        st.info("Apenas um PDF foi carregado. Para mesclar, carregue múltiplos ficheiros na secção '1. Carregar Ficheiro(s) PDF' acima.")

    if st.session_state.files_to_merge:
        st.markdown("**Ficheiros carregados para mesclagem (reordene se necessário):**")
        # Funções de reordenação (precisam estar definidas antes de serem usadas como callback)
        def move_file_up(index_to_move):
            current_list = st.session_state.files_to_merge
            if index_to_move > 0:
                current_list.insert(index_to_move - 1, current_list.pop(index_to_move))
                st.session_state.files_to_merge = current_list
                st.session_state.processed_pdf_bytes_merge = None # Resetar output se a ordem mudar

        def move_file_down(index_to_move):
            current_list = st.session_state.files_to_merge
            if index_to_move < len(current_list) - 1:
                current_list.insert(index_to_move + 1, current_list.pop(index_to_move))
                st.session_state.files_to_merge = current_list
                st.session_state.processed_pdf_bytes_merge = None

        for i_merge_list, f_obj in enumerate(st.session_state.files_to_merge):
            cols_merge_list = st.columns([0.1, 0.1, 0.8])
            with cols_merge_list[0]:
                if i_merge_list > 0:
                    st.button("⬆️", key=f"up_{f_obj.file_id}_{i_merge_list}_v11_merge", on_click=move_file_up, args=(i_merge_list,), help="Mover para cima")
            with cols_merge_list[1]:
                if i_merge_list < len(st.session_state.files_to_merge) - 1:
                    st.button("⬇️", key=f"down_{f_obj.file_id}_{i_merge_list}_v11_merge", on_click=move_file_down, args=(i_merge_list,), help="Mover para baixo")
            with cols_merge_list[2]:
                st.write(f"{i_merge_list+1}. {f_obj.name} ({round(f_obj.size / (1024*1024), 2)} MB)")
        st.markdown("---")

        optimize_merged_pdf = st.checkbox("Otimizar PDF mesclado ao salvar", value=True, key="optimize_merged_pdf_v11_merge")
        if st.button("Mesclar PDFs na Ordem Acima", key="process_merge_button_v11_merge", disabled=st.session_state.get('processing_merge', False) or len(st.session_state.files_to_merge) < 1):
            if not st.session_state.files_to_merge:
                st.warning("Por favor, carregue pelo menos um ficheiro PDF para processar.")
            elif len(st.session_state.files_to_merge) == 1:
                st.info("Apenas um ficheiro carregado. A 'mesclagem' resultará numa cópia deste ficheiro.")

            st.session_state.processing_merge = True
            st.session_state.processed_pdf_bytes_merge = None
            st.session_state.error_message = None
            merged_doc_obj = None
            merge_progress_bar = st.progress(0, text="Iniciando mesclagem...")

            with st.spinner(f"A mesclar {len(st.session_state.files_to_merge)} ficheiro(s) PDF... Por favor, aguarde."):
                try:
                    merged_doc_obj = fitz.open()
                    total_files_to_merge = len(st.session_state.files_to_merge)
                    for i_merge_proc, file_to_insert_uploaded_file in enumerate(st.session_state.files_to_merge):
                        progress_text = f"Adicionando ficheiro {i_merge_proc+1}/{total_files_to_merge}: {file_to_insert_uploaded_file.name}"
                        merge_progress_bar.progress(int(((i_merge_proc + 1) / total_files_to_merge) * 100), text=progress_text)
                        doc_to_insert = None
                        try:
                            # Usar getvalue() para obter os bytes do UploadedFile
                            doc_to_insert = fitz.open(stream=file_to_insert_uploaded_file.getvalue(), filetype="pdf")
                            merged_doc_obj.insert_pdf(doc_to_insert)
                        except Exception as e_inner_merge:
                            st.session_state.error_message = f"Erro ao processar o ficheiro '{file_to_insert_uploaded_file.name}': {e_inner_merge}"
                            st.error(st.session_state.error_message)
                            break # Interrompe a mesclagem se um arquivo falhar
                        finally:
                            if doc_to_insert: doc_to_insert.close()
                    
                    if not st.session_state.error_message: # Se não houve erro durante a inserção
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
                    st.error(st.session_state.error_message)
                    if merge_progress_bar and hasattr(merge_progress_bar, 'empty'): merge_progress_bar.empty()
                finally:
                    if merged_doc_obj: merged_doc_obj.close()
                    st.session_state.processing_merge = False
            st.rerun()

    if st.session_state.processed_pdf_bytes_merge:
        first_file_name = os.path.splitext(st.session_state.files_to_merge[0].name)[0] if st.session_state.files_to_merge else "mesclado"
        download_filename_merge = f"{first_file_name}_mesclado.pdf"
        if len(st.session_state.files_to_merge) > 1:
            download_filename_merge = f"{first_file_name}_e_outros_mesclado.pdf"
        elif len(st.session_state.files_to_merge) == 1:
             download_filename_merge = f"{first_file_name}_copia.pdf"
        st.download_button(label="Baixar PDF Mesclado", data=st.session_state.processed_pdf_bytes_merge, file_name=download_filename_merge, mime="application/pdf", key="download_merge_button_v11")

# Abas de edição (só se is_single_pdf_mode for True e doc_cached for válido)
tab_index_offset = 1
if st.session_state.is_single_pdf_mode and doc_cached:

    # --- ABA: REMOVER PÁGINAS ---
    with tabs[tab_index_offset]:
        st.header("Remover Páginas do PDF")
        with st.expander("Excluir por Marcadores", expanded=True):
            st.session_state.bookmark_search_term_remove = st.text_input(
                "Pesquisar em marcadores:", 
                value=st.session_state.get('bookmark_search_term_remove', ""), 
                key="bookmark_search_remove_input"
            ).lower()

            if st.session_state.bookmarks_data:
                st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
                with st.container(height=300):
                    for bm in st.session_state.bookmarks_data:
                        checkbox_key = f"delete_bookmark_{bm['id']}_tab_remove_v11_opt_ux"
                        # Inicializa o estado do checkbox se não existir
                        if checkbox_key not in st.session_state:
                            st.session_state[checkbox_key] = False
                        
                        # Filtra a exibição, mas o estado é persistente
                        if not st.session_state.bookmark_search_term_remove or st.session_state.bookmark_search_term_remove in bm['display_text'].lower():
                            st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado neste PDF para seleção.")

        with st.expander("Excluir por Números de Página", expanded=True):
            direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove_v11_opt_ux")
        
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox_tab_remove_v11_opt_ux")
        if st.button("Processar Remoção de Páginas", key="process_remove_button_tab_remove_v11_opt_ux", disabled=st.session_state.get('processing_remove', False)):
            st.session_state.processing_remove = True
            st.session_state.processed_pdf_bytes_remove = None
            st.session_state.error_message = None
            doc_to_modify = None
            with st.spinner("A processar remoção de páginas... Por favor, aguarde."):
                try:
                    # doc_cached já está carregado e é um objeto fitz.Document
                    # Para modificar, criamos uma cópia em memória para não alterar o doc_cached original
                    doc_to_modify = fitz.open(stream=doc_cached.write(), filetype="pdf")
                    
                    selected_bookmark_pages_to_delete = set()
                    if st.session_state.bookmarks_data:
                        for bm in st.session_state.bookmarks_data:
                            if st.session_state.get(f"delete_bookmark_{bm['id']}_tab_remove_v11_opt_ux", False):
                                for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                    selected_bookmark_pages_to_delete.add(page_num)
                    
                    direct_pages_to_delete_list = parse_page_input(direct_pages_str_tab_remove, doc_to_modify.page_count)
                    all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

                    if not all_pages_to_delete_0_indexed:
                        st.warning("Nenhuma página selecionada para exclusão.")
                    elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                        st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."
                        st.error(st.session_state.error_message)
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
                    st.error(st.session_state.error_message)
                finally:
                    if doc_to_modify: doc_to_modify.close()
                    st.session_state.processing_remove = False
            st.rerun()

        if st.session_state.processed_pdf_bytes_remove:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_removido.pdf"
            st.download_button(label="Baixar PDF com Páginas Removidas", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button_tab_remove_v11_opt_ux")

    # --- ABA: DIVIDIR PDF ---
    if len(tabs) > tab_index_offset + 1:
        with tabs[tab_index_offset + 1]:
            st.header("Dividir PDF")
            split_method = st.radio("Método de Divisão:", ("Por Tamanho Máximo (MB)", "A Cada N Páginas"), key="split_method_radio_tab_split_v11_opt_ux")
            optimize_pdf_split = st.checkbox("Otimizar partes divididas", value=True, key="optimize_pdf_split_checkbox_tab_split_v11_opt_ux")

            if split_method == "Por Tamanho Máximo (MB)":
                max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=5.0, step=0.1, format="%.1f", key="max_size_mb_input_tab_split_v11_opt_ux")
                if st.button("Dividir por Tamanho", key="split_by_size_button_tab_split_v11_opt_ux", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = []
                    st.session_state.error_message = None
                    # Implementação da divisão por tamanho é complexa e geralmente requer tentativa e erro ou bibliotecas especializadas.
                    # PyMuPDF não tem uma função direta para "dividir por tamanho de arquivo".
                    # Esta é uma simplificação/placeholder. Uma implementação real seria mais elaborada.
                    st.warning("A divisão por tamanho máximo de ficheiro é uma funcionalidade complexa de implementar com precisão e não está totalmente funcional nesta versão simplificada. Considere dividir por número de páginas.")
                    # Placeholder: apenas copia o doc original para ilustrar
                    # try:
                    #     temp_doc = fitz.open(stream=doc_cached.write(), filetype="pdf")
                    #     buffer = io.BytesIO()
                    #     temp_doc.save(buffer) # Não otimizado aqui, só para ter os bytes
                    #     st.session_state.split_pdf_parts.append({"name": f"{os.path.splitext(st.session_state.pdf_name)[0]}_parte1.pdf", "data": buffer.getvalue()})
                    #     temp_doc.close()
                    #     st.success("Divisão por tamanho (simulada) concluída.")
                    # except Exception as e_split_size:
                    #     st.session_state.error_message = f"Erro na divisão por tamanho (simulada): {e_split_size}"
                    #     st.error(st.session_state.error_message)
                    st.session_state.processing_split = False
                    st.rerun()

            elif split_method == "A Cada N Páginas":
                pages_per_split_val = st.number_input("Número de páginas por parte:", min_value=1, value=max(1, st.session_state.current_page_count_for_inputs // 10 if st.session_state.current_page_count_for_inputs > 0 else 10), step=1, key="pages_per_split_input_tab_split_v11_opt_ux")
                if st.button("Dividir por Número de Páginas", key="split_by_count_button_tab_split_v11_opt_ux", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = []
                    st.session_state.error_message = None
                    progress_bar_split_count = st.progress(0, text="Iniciando divisão por contagem...")
                    
                    original_doc_for_split_count = None
                    try:
                        original_doc_for_split_count = fitz.open(stream=doc_cached.write(), filetype="pdf")
                        total_pages_original = original_doc_for_split_count.page_count
                        part_number = 1
                        num_parts_expected = (total_pages_original + pages_per_split_val - 1) // pages_per_split_val if pages_per_split_val > 0 else 0

                        for i_split_count in range(0, total_pages_original, pages_per_split_val):
                            progress_text_val = f"Criando parte {part_number}/{num_parts_expected}..."
                            progress_value = int((part_number / num_parts_expected) * 100) if num_parts_expected > 0 else 0
                            progress_bar_split_count.progress(progress_value, text=progress_text_val)

                            new_part_doc = fitz.open() # Novo PDF para a parte
                            new_part_doc.insert_pdf(original_doc_for_split_count, from_page=i_split_count, to_page=min(i_split_count + pages_per_split_val - 1, total_pages_original - 1))
                            
                            part_buffer = io.BytesIO()
                            save_options_split = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_split:
                                save_options_split.update({"deflate_images": True, "deflate_fonts": True})
                            new_part_doc.save(part_buffer, **save_options_split)
                            new_part_doc.close()
                            
                            part_name = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parte{part_number}.pdf"
                            st.session_state.split_pdf_parts.append({"name": part_name, "data": part_buffer.getvalue()})
                            part_number += 1
                        
                        if progress_bar_split_count: progress_bar_split_count.empty()
                        st.success(f"{len(st.session_state.split_pdf_parts)} partes criadas com sucesso!")
                    except Exception as e_split_count:
                        st.session_state.error_message = f"Erro ao dividir por número de páginas: {e_split_count}"
                        st.error(st.session_state.error_message)
                        if progress_bar_split_count: progress_bar_split_count.empty()
                    finally:
                        if original_doc_for_split_count: original_doc_for_split_count.close()
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
                st.download_button(label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP", data=zip_buffer, file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip", mime="application/zip", key="download_zip_button_tab_split_v11_opt_ux")
                st.markdown("---")
                for i_part_dl, part_data in enumerate(st.session_state.split_pdf_parts):
                    st.download_button(label=f"Baixar {part_data['name']}", data=part_data["data"], file_name=part_data["name"], mime="application/pdf", key=f"download_part_{i_part_dl}_button_tab_split_v11_opt_ux")

    # --- ABA: EXTRAIR PÁGINAS ---
    if len(tabs) > tab_index_offset + 2:
        with tabs[tab_index_offset + 2]:
            st.header("Extrair Páginas Específicas")
            with st.expander("Extrair por Marcadores", expanded=False):
                st.session_state.bookmark_search_term_extract = st.text_input(
                    "Pesquisar em marcadores:", 
                    value=st.session_state.get('bookmark_search_term_extract', ""), 
                    key="bookmark_search_extract_input"
                ).lower()

                if st.session_state.bookmarks_data:
                    st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja extrair.")
                    with st.container(height=200):
                        for bm in st.session_state.bookmarks_data:
                            checkbox_key = f"extract_bookmark_{bm['id']}_tab_extract_v11_opt_ux"
                            if checkbox_key not in st.session_state:
                                st.session_state[checkbox_key] = False
                            
                            if not st.session_state.bookmark_search_term_extract or st.session_state.bookmark_search_term_extract in bm['display_text'].lower():
                                st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
                else:
                    st.info("Nenhum marcador encontrado neste PDF para seleção.")

            with st.expander("Extrair por Números de Página", expanded=True):
                extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract_v11_opt_ux")
            
            optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract_v11_opt_ux")
            if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract_v11_opt_ux", disabled=st.session_state.get('processing_extract', False)):
                st.session_state.processing_extract = True
                st.session_state.processed_pdf_bytes_extract = None
                st.session_state.error_message = None
                new_extracted_doc = None
                with st.spinner("A processar extração de páginas... Por favor, aguarde."):
                    try:
                        # doc_cached é o documento original
                        selected_bookmark_pages_to_extract = set()
                        if st.session_state.bookmarks_data:
                            for bm in st.session_state.bookmarks_data:
                                if st.session_state.get(f"extract_bookmark_{bm['id']}_tab_extract_v11_opt_ux", False):
                                    for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                        selected_bookmark_pages_to_extract.add(page_num)
                        
                        direct_pages_to_extract_list = parse_page_input(extract_pages_str, doc_cached.page_count)
                        all_pages_to_extract_0_indexed = sorted(list(selected_bookmark_pages_to_extract.union(set(direct_pages_to_extract_list))))

                        if not all_pages_to_extract_0_indexed:
                            st.warning("Nenhuma página selecionada para extração.")
                        else:
                            new_extracted_doc = fitz.open() # Cria um novo PDF em branco
                            new_extracted_doc.insert_pdf(doc_cached, from_page=0, to_page=doc_cached.page_count-1, selected_pages=all_pages_to_extract_0_indexed)

                            save_options_extract = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_extract:
                                save_options_extract.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            new_extracted_doc.save(pdf_output_buffer, **save_options_extract)
                            st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                            st.success(f"PDF processado! {len(all_pages_to_extract_0_indexed)} página(s) extraída(s).")
                    except Exception as e_extract:
                        st.session_state.error_message = f"Erro ao extrair páginas: {e_extract}"
                        st.error(st.session_state.error_message)
                    finally:
                        if new_extracted_doc: new_extracted_doc.close()
                        st.session_state.processing_extract = False
                st.rerun()

            if st.session_state.processed_pdf_bytes_extract:
                download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
                st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract_v11_opt_ux")

    # --- ABA: GERIR PÁGINAS VISUALMENTE ---
    if len(tabs) > tab_index_offset + 3:
        with tabs[tab_index_offset + 3]:
            st.header("Gerir Páginas Visualmente")

            if not st.session_state.get('active_tab_visual_preview_ready', False) and doc_cached and not st.session_state.generating_previews:
                st.session_state.generating_previews = True
                with st.spinner("Gerando pré-visualizações das páginas..."):
                    previews = []
                    preview_progress = st.progress(0, text="Iniciando geração de previews...")
                    total_pages_for_preview = doc_cached.page_count
                    for i_prev_gen in range(total_pages_for_preview):
                        preview_progress.progress(int(((i_prev_gen + 1) / total_pages_for_preview) * 100), text=f"Gerando preview da página {i_prev_gen + 1}/{total_pages_for_preview}")
                        page_img = doc_cached.load_page(i_prev_gen).get_pixmap(dpi=72) # DPI baixo para previews rápidas
                        img_byte_arr = io.BytesIO()
                        img = Image.frombytes("RGB", [page_img.width, page_img.height], page_img.samples)
                        img.save(img_byte_arr, format='PNG')
                        previews.append(img_byte_arr.getvalue())
                    st.session_state.page_previews = previews
                    if preview_progress: preview_progress.empty()
                    st.session_state.generating_previews = False
                    st.session_state.active_tab_visual_preview_ready = True
                st.rerun()
            
            if not st.session_state.page_previews:
                st.info("As pré-visualizações das páginas serão geradas. Se não aparecerem, recarregue ou clique novamente nesta aba.")
            else:
                st.markdown(f"Total de páginas: {len(st.session_state.page_previews)}. Selecione as páginas abaixo:")
                num_cols_preview = st.sidebar.slider("Colunas para pré-visualização:", 2, 8, 4, key="preview_cols_slider_v11_opt_ux")
                cols_preview_display = st.columns(num_cols_preview)
                
                for i_preview, img_bytes_preview in enumerate(st.session_state.page_previews):
                    with cols_preview_display[i_preview % num_cols_preview]:
                        page_key = f"select_page_preview_{i_preview}_v11_opt_ux"
                        if i_preview not in st.session_state.visual_page_selection: # Inicializa se não existir
                            st.session_state.visual_page_selection[i_preview] = False
                        
                        # Usar st.checkbox para permitir a seleção sobre a imagem
                        current_selection_state = st.session_state.visual_page_selection[i_preview]
                        new_selection_state = st.checkbox(f"Página {i_preview+1}", value=current_selection_state, key=page_key)
                        st.image(img_bytes_preview, width=120) # Manter a imagem visível
                        
                        if new_selection_state != current_selection_state:
                            st.session_state.visual_page_selection[i_preview] = new_selection_state
                            st.rerun() # Rerun para atualizar a lista de selecionadas imediatamente (opcional)

                selected_page_indices = sorted([idx for idx, selected in st.session_state.visual_page_selection.items() if selected])
                st.markdown(f"**Páginas selecionadas (base 0):** {selected_page_indices if selected_page_indices else 'Nenhuma'}")

                col_action1, col_action2 = st.columns(2)
                with col_action1:
                    if st.button("Excluir Páginas Selecionadas", key="delete_visual_button_tab_visual_v11_opt_ux", disabled=st.session_state.get('processing_visual_delete', False)):
                        st.session_state.processing_visual_delete = True
                        st.session_state.processed_pdf_bytes_visual = None
                        st.session_state.error_message = None
                        st.session_state.visual_action_type = "excluido_vis"

                        if not selected_page_indices:
                            st.warning("Nenhuma página selecionada para exclusão.")
                        else:
                            doc_visual_modify = None
                            try:
                                doc_visual_modify = fitz.open(stream=doc_cached.write(), filetype="pdf")
                                if len(selected_page_indices) >= doc_visual_modify.page_count:
                                    st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."
                                    st.error(st.session_state.error_message)
                                else:
                                    doc_visual_modify.delete_pages(selected_page_indices)
                                    save_options_visual = {"garbage": 4, "deflate": True, "clean": True} # Otimização padrão
                                    pdf_output_buffer = io.BytesIO()
                                    doc_visual_modify.save(pdf_output_buffer, **save_options_visual)
                                    st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                    st.success(f"{len(selected_page_indices)} página(s) excluída(s) visualmente.")
                                    st.session_state.visual_page_selection = {} # Limpa seleção
                                    st.session_state.active_tab_visual_preview_ready = False # Força regeneração das previews
                            except Exception as e_vis_del:
                                st.session_state.error_message = f"Erro ao excluir páginas visualmente: {e_vis_del}"
                                st.error(st.session_state.error_message)
                            finally:
                                if doc_visual_modify: doc_visual_modify.close()
                        st.session_state.processing_visual_delete = False
                        st.rerun()
                
                with col_action2:
                    if st.button("Extrair Páginas Selecionadas", key="extract_visual_button_tab_visual_v11_opt_ux", disabled=st.session_state.get('processing_visual_extract', False)):
                        st.session_state.processing_visual_extract = True
                        st.session_state.processed_pdf_bytes_visual = None
                        st.session_state.error_message = None
                        st.session_state.visual_action_type = "extraido_vis"

                        if not selected_page_indices:
                            st.warning("Nenhuma página selecionada para extração.")
                        else:
                            doc_visual_extract = None
                            try:
                                doc_visual_extract = fitz.open()
                                doc_visual_extract.insert_pdf(doc_cached, selected_pages=selected_page_indices)
                                save_options_visual = {"garbage": 4, "deflate": True, "clean": True} # Otimização padrão
                                pdf_output_buffer = io.BytesIO()
                                doc_visual_extract.save(pdf_output_buffer, **save_options_visual)
                                st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                st.success(f"{len(selected_page_indices)} página(s) extraída(s) visualmente.")
                                st.session_state.visual_page_selection = {} # Limpa seleção
                            except Exception as e_vis_ext:
                                st.session_state.error_message = f"Erro ao extrair páginas visualmente: {e_vis_ext}"
                                st.error(st.session_state.error_message)
                            finally:
                                if doc_visual_extract: doc_visual_extract.close()
                        st.session_state.processing_visual_extract = False
                        st.rerun()

                if st.session_state.processed_pdf_bytes_visual and st.session_state.visual_action_type:
                    action_type_label = st.session_state.visual_action_type.replace('_vis', '').replace('_', ' ')
                    download_filename_visual = f"{os.path.splitext(st.session_state.pdf_name)[0]}_{st.session_state.visual_action_type}.pdf"
                    st.download_button(label=f"Baixar PDF ({action_type_label})", data=st.session_state.processed_pdf_bytes_visual, file_name=download_filename_visual, mime="application/pdf", key="download_visual_button_tab_visual_v11_opt_ux")

    # --- ABA: OTIMIZAR PDF ---
    if len(tabs) > tab_index_offset + 4:
        with tabs[tab_index_offset + 4]:
            st.header("Otimizar PDF")
            st.markdown("Aplique otimizações ao PDF principal carregado para tentar reduzir o seu tamanho. Os resultados podem variar dependendo do conteúdo original do PDF.")
            
            optimization_profiles = {
                "Nenhuma": "Não aplica otimizações extras ao salvar (apenas limpeza básica).",
                "Leve (Rápida, Sem Perda de Qualidade Visual)": "Remove dados desnecessários e aplica compressão básica. Bom para limpeza rápida.",
                "Recomendada (Equilíbrio entre Tamanho e Qualidade)": "Limpeza mais profunda e compressão de imagens/fontes (geralmente sem perdas visíveis). Melhor para a maioria dos casos.",
                "Máxima Tentativa (Pode Afetar Qualidade de Imagens)": "Usa todas as opções de compressão sem perdas. A redução de tamanho em PDFs com muitas imagens pode ser limitada sem recompressão com perdas (não disponível aqui)."
            }
            selected_profile_name = st.selectbox(
                "Escolha um Perfil de Otimização:",
                options=list(optimization_profiles.keys()),
                index=2, # "Recomendada" como padrão
                help="Selecione o nível de otimização desejado.",
                key="optimize_profile_select_v11"
            )
            st.caption(optimization_profiles[selected_profile_name])

            if st.button("Otimizar PDF e Preparar Download", key="optimize_pdf_button_v11_opt_ux", disabled=st.session_state.get('processing_optimize', False)):
                st.session_state.processing_optimize = True
                st.session_state.processed_pdf_bytes_optimize = None
                st.session_state.error_message = None
                doc_to_optimize = None
                with st.spinner("A otimizar o PDF... Por favor, aguarde."):
                    try:
                        doc_to_optimize = fitz.open(stream=doc_cached.write(), filetype="pdf")
                        save_options_optimize = {"clean": True} # 'clean' é sempre bom

                        if selected_profile_name == "Leve (Rápida, Sem Perda de Qualidade Visual)":
                            save_options_optimize.update({"garbage": 2, "deflate": True})
                        elif selected_profile_name == "Recomendada (Equilíbrio entre Tamanho e Qualidade)":
                            save_options_optimize.update({"garbage": 4, "deflate": True, "deflate_images": True, "deflate_fonts": True})
                        elif selected_profile_name == "Máxima Tentativa (Pode Afetar Qualidade de Imagens)":
                            save_options_optimize.update({"garbage": 4, "deflate": True, "deflate_images": True, "deflate_fonts": True})
                        # Se "Nenhuma", save_options terá apenas "clean": True
                        
                        optimized_pdf_buffer = io.BytesIO()
                        doc_to_optimize.save(optimized_pdf_buffer, **save_options_optimize)
                        st.session_state.processed_pdf_bytes_optimize = optimized_pdf_buffer.getvalue()
                        
                        original_size_bytes = len(st.session_state.pdf_doc_bytes_original)
                        optimized_size_bytes = len(st.session_state.processed_pdf_bytes_optimize)
                        
                        st.success(f"PDF otimizado com o perfil '{selected_profile_name}'!")
                        st.info(f"Tamanho Original: {original_size_bytes / 1024:.2f} KB")
                        st.info(f"Tamanho Otimizado: {optimized_size_bytes / 1024:.2f} KB")
                        if original_size_bytes > 0 and optimized_size_bytes < original_size_bytes:
                            reduction_percent = ((original_size_bytes - optimized_size_bytes) / original_size_bytes) * 100
                            st.info(f"Redução de tamanho: {reduction_percent:.2f}%")
                        elif optimized_size_bytes >= original_size_bytes and selected_profile_name != "Nenhuma":
                            st.info("O tamanho do ficheiro não foi reduzido (pode até ter aumentado ligeiramente). Isto pode acontecer se o PDF já estiver bem otimizado ou devido à natureza do seu conteúdo.")
                        elif selected_profile_name == "Nenhuma":
                            st.info("Nenhuma otimização extra foi aplicada além da limpeza básica.")

                    except Exception as e_optimize:
                        st.session_state.error_message = f"Erro durante a otimização do PDF: {e_optimize}"
                        st.error(st.session_state.error_message)
                    finally:
                        if doc_to_optimize: doc_to_optimize.close()
                        st.session_state.processing_optimize = False
                st.rerun()

            if st.session_state.processed_pdf_bytes_optimize:
                download_filename_optimize = f"{os.path.splitext(st.session_state.pdf_name)[0]}_otimizado.pdf"
                st.download_button(label="Baixar PDF Otimizado", data=st.session_state.processed_pdf_bytes_optimize, file_name=download_filename_optimize, mime="application/pdf", key="download_optimized_pdf_button_v11_opt_ux")

# --- Fechar doc_cached se ainda estiver aberto no final do script ---
# Isso é importante para liberar recursos, especialmente se o objeto não for mais necessário
# ou antes de um rerun que possa carregar um novo arquivo.
# Contudo, com st.cache_data, o gerenciamento pode ser mais complexo.
# Se load_pdf_from_bytes retorna um objeto que deve ser fechado, o chamador é responsável.
# Neste fluxo, doc_cached é usado ao longo do script, então não o fechamos prematuramente.
# O ideal é que o Streamlit gerencie o ciclo de vida de objetos em cache ou que eles sejam auto-suficientes.
# Para fitz.Document, se não for mais usado em um rerun, ele será coletado pelo GC.
# A preocupação maior é se o objeto em si retém um handle de arquivo que não é liberado.
# Abrir de 'stream=pdf_bytes' geralmente é seguro.

# --- Exibir mensagem de erro global na sidebar ---
active_processing_flags = [
    st.session_state.get('processing_remove', False), st.session_state.get('processing_split', False),
    st.session_state.get('processing_extract', False), st.session_state.get('processing_visual_delete', False),
    st.session_state.get('processing_visual_extract', False), st.session_state.get('processing_merge', False),
    st.session_state.get('processing_optimize', False), st.session_state.get('generating_previews', False)
]

successful_outputs_exist = any([
    st.session_state.processed_pdf_bytes_remove, st.session_state.processed_pdf_bytes_extract,
    st.session_state.processed_pdf_bytes_visual, st.session_state.processed_pdf_bytes_merge,
    st.session_state.processed_pdf_bytes_optimize, bool(st.session_state.split_pdf_parts)
])

# Limpar erro se uma nova ação for iniciada ou um novo upload ocorrer
if any(active_processing_flags) or (uploaded_files and st.session_state.last_uploaded_file_ids != sorted([f.file_id for f in uploaded_files])):
    st.session_state.error_message = None

if st.session_state.error_message and not any(active_processing_flags) and not successful_outputs_exist:
    st.sidebar.error(f"Último erro: {st.session_state.error_message}")
    # Não limpar o erro aqui para que o usuário possa vê-lo até a próxima ação ou reset.
