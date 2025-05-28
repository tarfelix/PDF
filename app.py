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
if st.sidebar.button("Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn_v13"):
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
    key="main_pdf_uploader_v13"
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
if len(tab_titles_display) == 1: # Apenas Mesclar
    tab_merge, = st.tabs(tab_titles_display)
elif len(tab_titles_display) > 1 : # Mesclar + Abas de Edição
    tab_merge, tab_remove, tab_split, tab_extract, tab_visual_manage, tab_optimize = st.tabs(tab_titles_display)
else: # Caso de fallback (não deve acontecer com a lógica atual)
    tab_merge = st.tabs(tab_titles_display)[0] # Pelo menos a aba de mesclar

doc_cached = None 
if st.session_state.is_single_pdf_mode and st.session_state.pdf_doc_bytes_original:
    doc_cached_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if doc_cached_data and doc_cached_data[0]:
        doc_cached, _, _ = doc_cached_data
    else:
        st.error("Erro ao aceder ao PDF principal em cache. Por favor, recarregue o ficheiro.")
        st.session_state.is_single_pdf_mode = False 

# --- ABA: MESCLAR PDFS ---
with tab_merge: 
    # ... (Código da aba Mesclar, como na v12)
    # ... (Omitido para brevidade, mas é o mesmo da v12, com chaves atualizadas para v13)

# Abas de edição (só se is_single_pdf_mode for True e doc_cached for válido)
if st.session_state.is_single_pdf_mode and doc_cached:
    # --- ABA: REMOVER PÁGINAS ---
    with tab_remove: 
        st.header("Remover Páginas do PDF")
        # ... (Conteúdo completo da aba Remover Páginas, como na v12)
        # ... (Omitido para brevidade)

    # --- ABA: DIVIDIR PDF ---
    with tab_split:
        st.header("Dividir PDF")
        # ... (Conteúdo completo da aba Dividir PDF, como na v12)
        # ... (Omitido para brevidade)

    # --- ABA: EXTRAIR PÁGINAS ---
    with tab_extract:
        st.header("Extrair Páginas Específicas")
        with st.expander("Extrair por Marcadores", expanded=False): 
            st.text_input(
                "Pesquisar nos marcadores:", 
                key="search_term_extract_bookmarks" 
            )
            if st.session_state.bookmarks_data:
                search_term_extract = st.session_state.get("search_term_extract_bookmarks", "").lower()
                filtered_bookmarks_extract = [
                    bm for bm in st.session_state.bookmarks_data
                    if search_term_extract in bm['title'].lower()
                ] if search_term_extract else st.session_state.bookmarks_data
                
                if not filtered_bookmarks_extract and search_term_extract:
                    st.caption("Nenhum marcador encontrado com o termo pesquisado.")
                elif not st.session_state.bookmarks_data:
                     st.info("Este PDF não contém marcadores.")
                else:
                    st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja extrair.")
                    with st.container(height=200): 
                        for bm in filtered_bookmarks_extract:
                            checkbox_key = f"extract_bookmark_{bm['id']}_tab_extract_v13" 
                            if checkbox_key not in st.session_state: 
                                st.session_state[checkbox_key] = False
                            st.checkbox(label=bm['display_text'], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado neste PDF.")
        with st.expander("Extrair por Números de Página", expanded=True):
            extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract_v13")
        optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract_v13")
        
        if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract_v13", disabled=st.session_state.get('processing_extract', False)):
            st.session_state.processing_extract = True
            st.session_state.processed_pdf_bytes_extract = None; st.session_state.error_message = None
            doc_original_for_extract = None; new_extracted_doc = None
            with st.spinner("A extrair páginas... Por favor, aguarde."):
                try:
                    doc_original_for_extract = fitz.open(stream=doc_cached.write(), filetype="pdf") 
                    selected_bookmark_pages_to_extract = set()
                    if st.session_state.bookmarks_data:
                        for bm in st.session_state.bookmarks_data:
                            if st.session_state.get(f"extract_bookmark_{bm['id']}_tab_extract_v13", False):
                                for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                    selected_bookmark_pages_to_extract.add(page_num)
                    direct_pages_to_extract_list = parse_page_input(extract_pages_str, doc_original_for_extract.page_count)
                    all_pages_to_extract_0_indexed = sorted(list(selected_bookmark_pages_to_extract.union(set(direct_pages_to_extract_list))))
                    
                    if not all_pages_to_extract_0_indexed: 
                        st.warning("Nenhuma página (via marcador ou direta) especificada para extração.")
                    else:
                        new_extracted_doc = fitz.open()
                        valid_pages_to_extract = [p for p in all_pages_to_extract_0_indexed if 0 <= p < doc_original_for_extract.page_count]
                        
                        if not valid_pages_to_extract:
                            st.warning("Nenhuma página válida selecionada para extração após verificação de intervalo.")
                        else:
                            for page_index in valid_pages_to_extract: # Inserir página por página
                                new_extracted_doc.insert_pdf(doc_original_for_extract, from_page=page_index, to_page=page_index)
                            
                            if len(new_extracted_doc) > 0: 
                                save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_pdf_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                                pdf_output_buffer = io.BytesIO()
                                new_extracted_doc.save(pdf_output_buffer, **save_options); pdf_output_buffer.seek(0)
                                st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                                st.success(f"PDF com {len(new_extracted_doc)} página(s) extraída(s) pronto!")
                            else:
                                st.warning("Nenhuma página foi efetivamente extraída para o novo documento.")
                except Exception as e: 
                    st.session_state.error_message = f"Erro ao extrair páginas: {e}"; st.error(st.session_state.error_message)
                finally: 
                    if doc_original_for_extract: doc_original_for_extract.close()
                    if new_extracted_doc: new_extracted_doc.close()
            st.session_state.processing_extract = False
            st.rerun()
        
        if st.session_state.processed_pdf_bytes_extract:
            download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
            st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract_v13")

    # --- ABA: GERIR PÁGINAS VISUALMENTE ---
    with tab_visual_manage:
        # ... (Lógica da aba Visual, como na v12, com a correção para extração se necessário)
        st.header("Gerir Páginas Visualmente")
        # ... (conteúdo omitido para brevidade)

    # --- ABA: OTIMIZAR PDF ---
    with tab_optimize:
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

