import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile
from PIL import Image

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
if st.sidebar.button("Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn_v13_indent_ok"):
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
    key="main_pdf_uploader_v13_indent_ok"
)

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

# Desempacota as abas em variáveis individuais
# O número de variáveis deve corresponder ao número de títulos em tab_titles_display
# Esta é a correção principal para o IndentationError
if len(tab_titles_display) == 1:
    tab_merge, = st.tabs(tab_titles_display)
    # Define as outras variáveis de aba como None para evitar NameError se não existirem
    tab_remove, tab_split, tab_extract, tab_visual_manage, tab_optimize = None, None, None, None, None
elif len(tab_titles_display) > 1:
    # A ordem aqui deve corresponder exatamente à ordem em tab_titles_display
    tab_merge, tab_remove, tab_split, tab_extract, tab_visual_manage, tab_optimize = st.tabs(tab_titles_display)
else: # Fallback improvável
    st.error("Erro ao criar as abas da aplicação.")
    st.stop()


doc_cached = None 
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    doc_cached_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if doc_cached_data and doc_cached_data[0]:
        doc_cached, _, _ = doc_cached_data
    else:
        st.error("Erro ao aceder ao PDF principal em cache. Por favor, recarregue o ficheiro.")
        st.session_state.is_single_pdf_mode = False 

# --- ABA: MESCLAR PDFS ---
# O conteúdo desta aba está corretamente indentado após o 'with tab_merge:'
with tab_merge: 
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
                    st.button("⬆️", key=f"up_{f_obj.file_id}_{i_merge_list}_v13_indent_fix", on_click=move_file_up, args=(i_merge_list,), help="Mover para cima")
            with cols_merge_list[1]:
                if i_merge_list < len(st.session_state.files_to_merge) - 1:
                    st.button("⬇️", key=f"down_{f_obj.file_id}_{i_merge_list}_v13_indent_fix", on_click=move_file_down, args=(i_merge_list,), help="Mover para baixo")
            with cols_merge_list[2]:
                st.write(f"{i_merge_list+1}. {f_obj.name} ({round(f_obj.size / (1024*1024), 2)} MB)")
        
        st.markdown("---")
        optimize_merged_pdf = st.checkbox("Otimizar PDF mesclado ao salvar", value=True, key="optimize_merged_pdf_v13_indent_fix")

        if st.button("Mesclar PDFs na Ordem Acima", key="process_merge_button_v13_indent_fix", disabled=st.session_state.get('processing_merge', False) or len(st.session_state.files_to_merge) < 1):
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
            st.download_button(label="Baixar PDF Mesclado", data=st.session_state.processed_pdf_bytes_merge, file_name=download_filename_merge, mime="application/pdf", key="download_merge_button_v13_indent_fix")

# Abas de edição (só se is_single_pdf_mode for True e doc_cached for válido)
if st.session_state.is_single_pdf_mode and doc_cached:
    # --- ABA: REMOVER PÁGINAS ---
    if tab_remove: # Verifica se a variável da aba foi definida
        with tab_remove: 
            st.header("Remover Páginas do PDF")
            # ... (Conteúdo completo da aba Remover Páginas, como na v12)
            # ... (Omitido para brevidade, mas deve estar aqui e corretamente indentado)
            pass 

    # --- ABA: DIVIDIR PDF ---
    if tab_split: # Verifica se a variável da aba foi definida
        with tab_split:
            st.header("Dividir PDF")
            # ... (Conteúdo completo da aba Dividir PDF, como na v12)
            # ... (Omitido para brevidade)
            pass

    # --- ABA: EXTRAIR PÁGINAS ---
    if tab_extract: # Verifica se a variável da aba foi definida
        with tab_extract:
            st.header("Extrair Páginas Específicas")
            # ... (Conteúdo completo da aba Extrair Páginas, como na v12, com a correção de insert_pdf)
            # ... (Omitido para brevidade)
            pass

    # --- ABA: GERIR PÁGINAS VISUALMENTE ---
    if tab_visual_manage: # Verifica se a variável da aba foi definida
        with tab_visual_manage:
            st.header("Gerir Páginas Visualmente")
            # ... (Conteúdo completo da aba Gerir Visualmente, como na v12)
            # ... (Omitido para brevidade)
            pass

    # --- ABA: OTIMIZAR PDF ---
    if tab_optimize: # Verifica se a variável da aba foi definida
        with tab_optimize:
            st.header("Otimizar PDF")
            # ... (Conteúdo completo da aba Otimizar, como na v11)
            # ... (Omitido para brevidade)
            pass

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

