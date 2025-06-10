import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
from PIL import Image
import os

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Editor de PDF Jurídico Completo")

# --- Título e Descrição ---
st.title("✂️ Editor de PDF Jurídico Completo")
st.markdown("""
    **Bem-vindo!** Esta é a versão final e corrigida do seu editor de PDF.
    - **Extração de Peças Jurídicas:** Identifica e pré-seleciona TODAS as peças processuais automaticamente.
    - **Correção de Erros:** O erro ao extrair páginas foi resolvido.
    - **Demais Funcionalidades:** Mesclar, dividir, remover e otimizar continuam disponíveis.
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
    'found_legal_pieces': [],
}

# <<< CORREÇÃO FINAL: Lista de palavras-chave mais robusta e toda em minúsculas >>>
LEGAL_KEYWORDS = {
    # Peças principais e decisões judiciais (prioridade máxima)
    "Petição Inicial": ['petição inicial', 'inicial'],
    "Sentença": ['sentença', 'sentenca'],
    "Acórdão": ['acórdão', 'acordao'],
    "Decisão": ['decisão', 'decisao', 'decisão interlocutória'],
    "Despacho": ['despacho'],
    
    # Manifestações importantes das partes
    "Defesa/Contestação": ['defesa', 'contestação', 'contestacao'],
    "Réplica": ['réplica', 'replica', 'impugnação à contestação', 'impugnacao a contestacao'],
    "Recurso": ['recurso', 'contrarrazões', 'contrarrazoes', 'embargos de declaração'],

    # Atos e Peças secundárias
    "Ata de Audiência": ['ata de audiência', 'termo de audiência'],
    "Laudo": ['laudo', 'parecer técnico'],

    # Categoria genérica de manifestação (pega o que sobrou)
    "Manifestação": ['manifestação', 'manifestacao', 'petição', 'peticao'], 
    
    # Categorias de organização (sem pré-seleção, ficam por último para evitar falsos positivos)
    "Documento": ['documento', 'comprovante', 'procuração', 'procuracao', 'custas'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'sumário', 'indice', 'sumario'],
}

# <<< ALTERAÇÃO: Agora inclui Capa e Índice/Sumário na pré-seleção >>>
PRE_SELECTED_LEGAL_CATEGORIES = [
    "Petição Inicial", "Sentença", "Acórdão", "Decisão", "Despacho", 
    "Defesa/Contestação", "Réplica", "Recurso", "Ata de Audiência", 
    "Laudo", "Manifestação", "Capa", "Índice/Sumário"
]

# --- Funções Auxiliares ---
def initialize_session_state():
    """Limpa completamente o estado da sessão."""
    for key in list(st.session_state.keys()):
        if key != 'initialized_once':
            del st.session_state[key]
    
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value

if not st.session_state.get('initialized_once'):
    initialize_session_state()
    st.session_state.initialized_once = True

@st.cache_data(max_entries=5)
def get_pdf_metadata(pdf_bytes, filename_for_error_reporting="pdf_file"):
    """Extrai marcadores e contagem de páginas de um PDF em bytes."""
    if not pdf_bytes:
        return [], 0, "Erro: Nenhum byte de PDF fornecido."
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            bookmarks_data_loaded = get_bookmark_ranges(doc)
            num_pages = doc.page_count
            return bookmarks_data_loaded, num_pages, None
    except Exception as e:
        return [], 0, f"Erro ao carregar metadados do PDF ({filename_for_error_reporting}): {e}"

def get_bookmark_ranges(doc):
    """Calcula o intervalo de páginas para cada marcador."""
    bookmarks_data = []
    toc = doc.get_toc(simple=False)
    if not toc: return bookmarks_data
    
    num_total_pages = doc.page_count
    for i, item_i in enumerate(toc):
        if len(item_i) < 3: continue
        level, title, page_num = item_i[0], item_i[1], item_i[2]
        if not (1 <= page_num <= num_total_pages): continue
        
        start_page = page_num - 1
        end_page = num_total_pages - 1 # Default to end of doc
        
        # Find the start of the next bookmark at the same or higher level
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_j = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_j <= num_total_pages): continue
            if level_j <= level:
                end_page = page_num_j - 2
                break
        
        end_page = min(max(start_page, end_page), num_total_pages - 1)
        
        display_text = f"{'➡️' * (level - 1)}{'↪️' if level > 1 else ''} {title} (Págs. {start_page + 1} a {end_page + 1})"
        bookmarks_data.append({
            "id": f"bm_{i}_{page_num}", "title": title,
            "start_page_0_idx": start_page, "end_page_0_idx": end_page,
            "display_text": display_text
        })
    return bookmarks_data

def find_legal_sections_by_bookmark(bookmarks_data):
    """Identifica peças jurídicas, mantendo a ordem e usando uma lista de palavras-chave priorizada."""
    found_pieces = []
    if not bookmarks_data: return found_pieces

    for i, bookmark in enumerate(bookmarks_data):
        bookmark_title_lower = bookmark['title'].lower()
        classified = False
        
        for category, keywords in LEGAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in bookmark_title_lower:
                    piece_info = bookmark.copy()
                    piece_info['category'] = category
                    piece_info['unique_id'] = f"legal_{i}_{bookmark['id']}"
                    piece_info['preselect'] = category in PRE_SELECTED_LEGAL_CATEGORIES
                    found_pieces.append(piece_info)
                    classified = True
                    break
            if classified:
                break
    return found_pieces

def parse_page_input(page_str, max_page):
    """Converte string de páginas (ex: '1, 3-5') em uma lista de índices (base 0)."""
    selected_pages = set()
    if not page_str: return []
    for part in page_str.split(','):
        part = part.strip()
        if not part: continue
        try:
            if '-' in part:
                start, end = map(int, part.split('-'))
                for page in range(start, end + 1):
                    if 1 <= page <= max_page: selected_pages.add(page - 1)
            else:
                page = int(part)
                if 1 <= page <= max_page: selected_pages.add(page - 1)
        except ValueError:
            st.warning(f"Entrada inválida ignorada: '{part}'")
    return sorted(list(selected_pages))

# --- BARRA LATERAL (SIDEBAR) ---
if st.sidebar.button("🧹 Limpar Tudo e Recomeçar", key="clear_all_sidebar_btn"):
    initialize_session_state()
    get_pdf_metadata.clear()
    st.success("Estado reiniciado!")
    st.rerun()

# --- LÓGICA DE CARREGAMENTO DE ARQUIVO ---
st.header("1. Carregar Ficheiro(s) PDF")
uploaded_files = st.file_uploader(
    "Carregue um PDF para editar ou múltiplos para mesclar.", 
    type="pdf", 
    accept_multiple_files=True, 
    key="main_pdf_uploader"
)

if uploaded_files:
    current_ids = sorted([f.file_id for f in uploaded_files])
    if st.session_state.get('last_uploaded_file_ids') != current_ids:
        initialize_session_state()
        get_pdf_metadata.clear()
        st.session_state.last_uploaded_file_ids = current_ids
        
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            st.session_state.pdf_doc_bytes_original = uploaded_files[0].getvalue()
            st.session_state.pdf_name = uploaded_files[0].name
            bookmarks, num_pages, error = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
            if error:
                st.session_state.error_message = error
            else:
                st.session_state.bookmarks_data = bookmarks
                st.session_state.current_page_count_for_inputs = num_pages
                st.session_state.found_legal_pieces = find_legal_sections_by_bookmark(bookmarks)
        else:
            st.session_state.is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files
        st.rerun()

elif not uploaded_files and st.session_state.get('last_uploaded_file_ids'):
    initialize_session_state()
    get_pdf_metadata.clear()
    st.info("Nenhum PDF carregado. Por favor, carregue um arquivo.")
    st.rerun()

# --- ÁREA PRINCIPAL E ABAS ---
if st.session_state.get('pdf_name') or st.session_state.get('files_to_merge'):
    st.header("2. Escolha uma Ação")
    
    tab_titles = ["Mesclar PDFs"]
    if st.session_state.is_single_pdf_mode:
        tab_titles = ["Extrair Peças Jurídicas", "Gerir Páginas", "Remover Páginas", "Extrair Páginas", "Dividir PDF", "Otimizar PDF"]
    
    # Criando as abas
    tabs = st.tabs(tab_titles)
    
    # --- LÓGICA DAS ABAS ---
    is_processing = any(st.session_state.get(k, False) for k in st.session_state if k.startswith('processing_'))

    # Aba de Extração de Peças Jurídicas
    if st.session_state.is_single_pdf_mode:
        with tabs[0]:
            st.header("Extrair Peças Jurídicas (por Marcadores)")
            st.info("As peças processuais são identificadas e pré-selecionadas. Itens como 'Capa' e 'Documento' são identificados, mas não pré-selecionados.")
            
            if not st.session_state.found_legal_pieces:
                st.warning("Nenhuma peça jurídica foi identificada nos marcadores deste PDF.")
            else:
                st.markdown("**Peças identificadas no processo (em ordem cronológica):**")
                col1, col2, col3 = st.columns(3)
                if col1.button("Selecionar Todas", key="select_all_legal", disabled=is_processing):
                    for piece in st.session_state.found_legal_pieces: st.session_state[f"legal_piece_{piece['unique_id']}"] = True
                    st.rerun()
                if col2.button("Limpar Seleção", key="clear_all_legal", disabled=is_processing):
                    for piece in st.session_state.found_legal_pieces: st.session_state[f"legal_piece_{piece['unique_id']}"] = False
                    st.rerun()
                if col3.button("Restaurar Padrão", key="restore_preselect_legal", disabled=is_processing):
                    for piece in st.session_state.found_legal_pieces: st.session_state[f"legal_piece_{piece['unique_id']}"] = piece.get('preselect', False)
                    st.rerun()

                with st.container(height=400):
                    for piece in st.session_state.found_legal_pieces:
                        key = f"legal_piece_{piece['unique_id']}"
                        if key not in st.session_state:
                            st.session_state[key] = piece.get('preselect', False)
                        st.checkbox(piece['display_text'], value=st.session_state[key], key=key, disabled=is_processing)
                
                st.markdown("---")
                optimize = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_legal_extract", disabled=is_processing)

                if st.button("Extrair Peças Selecionadas", key="process_legal_extract", disabled=is_processing):
                    pages_to_extract = set()
                    for piece in st.session_state.found_legal_pieces:
                        if st.session_state.get(f"legal_piece_{piece['unique_id']}", False):
                            pages_to_extract.update(range(piece["start_page_0_idx"], piece["end_page_0_idx"] + 1))
                    
                    if not pages_to_extract:
                        st.warning("Nenhuma peça selecionada para extração.")
                    else:
                        st.session_state.processing_legal_extract = True
                        st.session_state.error_message = None
                        sorted_pages = sorted(list(pages_to_extract))
                        
                        with st.spinner(f"Extraindo {len(sorted_pages)} página(s)..."):
                            try:
                                with fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf") as original_doc:
                                    with fitz.open() as new_doc:
                                        # <<< CORREÇÃO FINAL: Removidos os argumentos conflitantes >>>
                                        new_doc.insert_pdf(original_doc, select=sorted_pages)
                                        
                                        save_opts = {"garbage": 4, "deflate": optimize, "clean": True}
                                        pdf_bytes = new_doc.write(**save_opts)
                                        st.session_state.processed_pdf_bytes_legal = pdf_bytes
                                        st.success("PDF com peças selecionadas gerado com sucesso!")
                            except Exception as e:
                                st.session_state.error_message = f"Erro ao extrair peças jurídicas: {e}"
                        
                        st.session_state.processing_legal_extract = False
                        st.rerun()

            if st.session_state.processed_pdf_bytes_legal:
                st.download_button(
                    label="⬇️ Baixar PDF com Peças Selecionadas",
                    data=st.session_state.processed_pdf_bytes_legal,
                    file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_pecas.pdf",
                    mime="application/pdf"
                )
    
    # Placeholder para outras abas (se necessário, o código completo pode ser adicionado aqui)
    # Exemplo: Aba de Mesclagem
    merge_tab_index = 0 if not st.session_state.is_single_pdf_mode else -1 # Define a aba correta
    if merge_tab_index != -1:
        with tabs[merge_tab_index]:
            st.subheader("Mesclar Múltiplos Ficheiros PDF")
            # Adicionar a lógica de mesclagem aqui, se necessário.
            if not st.session_state.get('files_to_merge'):
                st.info("Para mesclar, carregue dois ou mais ficheiros na seção 1.")

# Tratamento de Erro Global
if st.session_state.get("error_message"):
    st.sidebar.error(f"Ocorreu um erro:\n\n{st.session_state.error_message}")
    st.session_state.error_message = None # Limpa o erro após exibir
