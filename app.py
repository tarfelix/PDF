import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile
from PIL import Image
import shutil # Para verificar a existência do Tesseract

# --- Configuração Inicial e Verificação de OCR ---
OCR_AVAILABLE = False
TESSERACT_PATH = shutil.which("tesseract")
if TESSERACT_PATH:
    OCR_AVAILABLE = True
else:
    print("Tesseract OCR não encontrado no PATH do sistema. Funcionalidade de OCR estará desabilitada.")

st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Avançado (PT-BR)")

st.title("✂️ Editor e Divisor de PDF Avançado")
st.markdown("""
    **Funcionalidades:**
    1.  **Remover Páginas:** Exclua seções com base em marcadores (bookmarks) ou números de página.
    2.  **Dividir PDF:** Por tamanho máximo de arquivo (MB) ou a cada N páginas.
    3.  **Extrair Páginas:** Crie um novo PDF com páginas selecionadas.
    4.  **Gerir Páginas Visualmente:** Pré-visualize e selecione páginas para exclusão ou extração.
    5.  **Aplicar OCR:** Converta PDFs baseados em imagem em PDFs pesquisáveis (requer Tesseract OCR e pacote de idioma português instalados no ambiente do servidor).
""")

# --- Dicionário Padrão para o Estado da Sessão (DEFINIDO FORA DA FUNÇÃO) ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_ocr': None,
    'split_pdf_parts': [], 'error_message': None, 'last_uploaded_filename': None,
    'page_previews': [], 'visual_page_selection': {}, 
    'processing_remove': False, 'processing_split': False, 'processing_extract': False, 
    'processing_visual_delete': False, 'processing_visual_extract': False, 'processing_ocr': False,
    'active_tab_for_preview': None, 'generating_previews': False,
    'current_page_count_for_inputs': 0 # Para validar inputs de página
}

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
            level_j, _, page_num_1_indexed_j = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j <= num_total_pages_doc): continue
            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j - 2; break 
        end_page_0_idx = min(max(start_page_0_idx, end_page_0_idx), num_total_pages_doc - 1)
        display_text = f"{'➡️' * level_i} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "title": title_i, "start_page_0_idx": start_page_0_idx,
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
                for i in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i <= max_page_1_idx: selected_pages_0_indexed.add(i - 1) 
                    else: st.warning(f"Aviso: Página {i} (entrada direta) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
            elif part: 
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx: selected_pages_0_indexed.add(page_num_1_idx - 1) 
                else: st.warning(f"Aviso: Página {page_num_1_idx} (entrada direta) está fora do intervalo (1-{max_page_1_idx}). Será ignorada.")
        except ValueError: st.warning(f"Aviso: Entrada de página inválida '{part}'. Será ignorada.")
    return sorted(list(selected_pages_0_indexed))

def apply_ocr_to_doc(doc_to_ocr):
    if not OCR_AVAILABLE:
        st.warning("Funcionalidade de OCR não está disponível (Tesseract OCR não configurado no servidor). O PDF será salvo sem OCR.")
        return False
    try:
        is_already_searchable = all(page.get_text("text") for page in doc_to_ocr if doc_to_ocr and len(doc_to_ocr) > 0) # Adicionado if doc_to_ocr
        if is_already_searchable and len(doc_to_ocr) > 0: # Adicionado if len(doc_to_ocr) > 0
            st.info("O PDF já parece ser pesquisável. OCR não será reaplicado.")
            return False 

        total_pages = len(doc_to_ocr)
        if total_pages == 0:
            st.info("Documento está vazio, OCR não aplicável.")
            return False
            
        ocr_progress_text = "Aplicando OCR (Português)... 0%"
        ocr_progress_bar = st.progress(0, text=ocr_progress_text)
        
        if hasattr(doc_to_ocr, "ocr_pdf"):
            doc_to_ocr.ocr_pdf(language="por") 
            ocr_progress_bar.progress(100, text="OCR Aplicado!")
            st.success("OCR aplicado com sucesso!")
            return True
        else:
            st.warning("Método `ocr_pdf` não encontrado no PyMuPDF. A funcionalidade de OCR pode não estar disponível ou requer uma versão mais recente do PyMuPDF. Verifique também se o Tesseract OCR está instalado no servidor.")
            ocr_progress_bar.empty()
            return False
    except Exception as e:
        st.error(f"Erro durante o processo de OCR: {e}. Verifique se o Tesseract OCR e o pacote de idioma 'por' estão instalados no servidor. O PDF será salvo sem OCR adicional.")
        if 'ocr_progress_bar' in locals(): ocr_progress_bar.empty()
        return False

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    for key, value in DEFAULT_STATE.items(): # Usa o DEFAULT_STATE global
        if key not in st.session_state:
            # Para tipos mutáveis, cria uma nova instância vazia
            st.session_state[key] = type(value)() if isinstance(value, (list, dict, set)) else value
initialize_session_state()

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar PDF Carregado e Seleções", key="clear_all_sidebar_btn_v7_fixed"):
    for key in DEFAULT_STATE.keys():
        if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
        elif key == 'visual_page_selection': st.session_state[key] = {}
        elif key.startswith('processing_'): st.session_state[key] = False
        else: st.session_state[key] = None
            
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or "_input" in k or "_checkbox" in k]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    
    load_pdf_from_bytes.clear() 
    st.success("Estado da aplicação limpo!")
    st.rerun()

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader_main_v7_fixed")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        for key in DEFAULT_STATE.keys():
            if key not in ['pdf_doc_bytes_original', 'pdf_name', 'last_uploaded_filename']:
                if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
                elif key == 'visual_page_selection': st.session_state[key] = {}
                elif key.startswith('processing_'): st.session_state[key] = False
                else: st.session_state[key] = None
        
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_")]
        for k_del in keys_to_delete:
            if k_del in st.session_state: del st.session_state[k_del]
        
        load_pdf_from_bytes.clear()
        doc_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
        if doc_data and doc_data[0]: # Verifica se doc_data e doc_data[0] (o documento) não são None
            _, bookmarks, page_count = doc_data
            st.info(f"PDF '{st.session_state.pdf_name}' carregado com {page_count} páginas.")
            st.session_state.bookmarks_data = bookmarks
            st.session_state.current_page_count_for_inputs = page_count
        else:
            st.session_state.pdf_doc_bytes_original = None
            st.session_state.current_page_count_for_inputs = 0
else:
    if st.session_state.last_uploaded_filename is not None:
        st.session_state.pdf_doc_bytes_original = None
        st.session_state.last_uploaded_filename = None
        st.session_state.current_page_count_for_inputs = 0
        load_pdf_from_bytes.clear()

# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original:
    doc_cached_data = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if not doc_cached_data or not doc_cached_data[0]:
        st.error("Não foi possível carregar o documento PDF em cache para processamento.")
    else:
        doc_cached, _, _ = doc_cached_data # Desempacota o documento do resultado do cache
        active_tabs = ["Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente", "Aplicar OCR"]
        
        # Usar st.query_params para tentar manter a aba ativa entre reruns (opcional, mas bom para UX)
        query_params = st.query_params
        default_tab_index = active_tabs.index(query_params.get("tab", [active_tabs[0]])[0]) if query_params.get("tab") else 0
        
        # A função st.tabs não retorna a aba ativa diretamente, então precisamos de um truque
        # ou de um componente de abas personalizado se quisermos saber qual aba está ativa.
        # Por simplicidade, vamos assumir que o usuário seleciona a aba e o conteúdo é renderizado.
        # Para o download, vamos diferenciar os botões de download por chaves únicas e verificar qual botão foi pressionado.

        tab_remove, tab_split, tab_extract, tab_visual_manage, tab_ocr = st.tabs(active_tabs)

        # --- ABA: REMOVER PÁGINAS ---
        with tab_remove:
            st.header("Remover Páginas do PDF")
            with st.expander("Excluir por Marcadores", expanded=True):
                if st.session_state.bookmarks_data:
                    st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
                    with st.container(height=300):
                        for bm in st.session_state.bookmarks_data:
                            checkbox_key = f"delete_bookmark_{bm['id']}_tab_remove_v7"
                            if checkbox_key not in st.session_state: st.session_state[checkbox_key] = False
                            st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
                else:
                    st.info("Nenhum marcador encontrado neste PDF para seleção.")

            with st.expander("Excluir por Números de Página", expanded=True):
                direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove_v7")
            
            optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox_tab_remove_v7")
            ocr_pdf_remove = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_remove_checkbox_tab_remove_v7", help="Requer Tesseract. Pode demorar.")
            
            if st.button("Processar Remoção de Páginas", key="process_remove_button_tab_remove_v7", disabled=st.session_state.get('processing_remove', False)):
                st.session_state.processing_remove = True
                st.session_state.processed_pdf_bytes_remove = None; st.session_state.error_message = None
                
                with st.spinner("A processar remoção de páginas... Por favor, aguarde."):
                    doc_to_modify = None
                    try:
                        doc_to_modify = fitz.open(stream=doc_cached.write(), filetype="pdf")
                        selected_bookmark_pages_to_delete = set()
                        if st.session_state.bookmarks_data:
                            for bm in st.session_state.bookmarks_data:
                                if st.session_state.get(f"delete_bookmark_{bm['id']}_tab_remove_v7", False):
                                    for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                        selected_bookmark_pages_to_delete.add(page_num)
                        direct_pages_to_delete_list = parse_page_input(direct_pages_str_tab_remove, doc_to_modify.page_count)
                        all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

                        if not all_pages_to_delete_0_indexed: st.warning("Nenhuma página selecionada para exclusão.")
                        elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                            st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."; st.error(st.session_state.error_message)
                        else:
                            doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                            if ocr_pdf_remove: apply_ocr_to_doc(doc_to_modify)
                            
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
                st.download_button(label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button_tab_remove_v7")

        # --- ABA: DIVIDIR PDF ---
        with tab_split:
            st.header("Dividir PDF")
            split_method = st.radio("Método de Divisão:", ("Por Tamanho Máximo (MB)", "A Cada N Páginas"), key="split_method_radio_tab_split_v7")
            optimize_pdf_split = st.checkbox("Otimizar partes divididas", value=True, key="optimize_pdf_split_checkbox_tab_split_v7")
            ocr_pdf_split = st.checkbox("Tornar partes pesquisáveis (OCR - Português)", value=False, key="ocr_pdf_split_checkbox_tab_split_v7", help="Requer Tesseract. Pode demorar.")
            
            if split_method == "Por Tamanho Máximo (MB)":
                max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=5.0, step=0.1, format="%.1f", key="max_size_mb_input_tab_split_v7")
                if st.button("Dividir por Tamanho", key="split_by_size_button_tab_split_v7", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = [] ; st.session_state.error_message = None
                    progress_bar_split_size = st.progress(0, text="Iniciando divisão por tamanho...")
                    with st.spinner("A dividir PDF por tamanho... Por favor, aguarde."):
                        max_size_bytes = int(max_size_mb * 1024 * 1024)
                        original_doc_for_split = None
                        try:
                            original_doc_for_split = fitz.open(stream=doc_cached.write(), filetype="pdf")
                            total_pages_original = original_doc_for_split.page_count; current_page_index = 0; part_number = 1
                            
                            while current_page_index < total_pages_original:
                                progress_bar_split_size.progress(int((current_page_index / total_pages_original) * 100) if total_pages_original > 0 else 0 , text=f"Processando página {current_page_index+1}/{total_pages_original} para parte {part_number}...")
                                new_part_doc = fitz.open(); pages_in_current_part = 0
                                while current_page_index < total_pages_original:
                                    temp_doc_for_size_check = fitz.open()
                                    if pages_in_current_part > 0: temp_doc_for_size_check.insert_pdf(new_part_doc)
                                    temp_doc_for_size_check.insert_pdf(original_doc_for_split, from_page=current_page_index, to_page=current_page_index)
                                    temp_buffer = io.BytesIO()
                                    save_options_check = {"garbage": 0, "deflate": optimize_pdf_split}
                                    if optimize_pdf_split: save_options_check.update({"deflate_images": True, "deflate_fonts": True})
                                    temp_doc_for_size_check.save(temp_buffer, **save_options_check)
                                    estimated_size = len(temp_buffer.getvalue()); temp_doc_for_size_check.close(); temp_buffer.close()
                                    if pages_in_current_part > 0 and estimated_size > max_size_bytes: break 
                                    new_part_doc.insert_pdf(original_doc_for_split, from_page=current_page_index, to_page=current_page_index)
                                    current_page_index += 1; pages_in_current_part += 1
                                    if estimated_size > max_size_bytes and pages_in_current_part == 1:
                                        st.warning(f"Página {current_page_index} excede o limite. Será parte separada."); break
                                if pages_in_current_part > 0:
                                    if ocr_pdf_split: apply_ocr_to_doc(new_part_doc)
                                    part_buffer = io.BytesIO()
                                    final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                                    if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                                    new_part_doc.save(part_buffer, **final_save_options); part_buffer.seek(0)
                                    part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteT{part_number}.pdf"
                                    st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                                    part_number += 1
                                new_part_doc.close()
                            if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                            else: st.warning("Não foi possível dividir o PDF.")
                        except Exception as e: st.session_state.error_message = f"Erro ao dividir PDF: {e}"; st.error(st.session_state.error_message)
                        finally:
                            if original_doc_for_split: original_doc_for_split.close()
                            progress_bar_split_size.empty()
                    st.session_state.processing_split = False
                    st.rerun()

            elif split_method == "A Cada N Páginas":
                pages_per_split = st.number_input("Número de páginas por parte:", min_value=1, value=10, step=1, key="pages_per_split_input_tab_split_v7")
                if st.button("Dividir por Número de Páginas", key="split_by_count_button_tab_split_v7", disabled=st.session_state.get('processing_split', False)):
                    st.session_state.processing_split = True
                    st.session_state.split_pdf_parts = []; st.session_state.error_message = None
                    progress_bar_split_count = st.progress(0, text="Iniciando divisão por contagem...")
                    with st.spinner("A dividir PDF por número de páginas... Por favor, aguarde."):
                        original_doc_for_split_count = None
                        try:
                            original_doc_for_split_count = fitz.open(stream=doc_cached.write(), filetype="pdf")
                            total_pages_original = original_doc_for_split_count.page_count; part_number = 1
                            num_parts_expected = (total_pages_original + pages_per_split - 1) // pages_per_split

                            for i in range(0, total_pages_original, pages_per_split):
                                progress_bar_split_count.progress(int((part_number / num_parts_expected) * 100) if num_parts_expected > 0 else 0, text=f"Criando parte {part_number}/{num_parts_expected}...")
                                new_part_doc = fitz.open()
                                start_page = i; end_page = min(i + pages_per_split - 1, total_pages_original - 1)
                                new_part_doc.insert_pdf(original_doc_for_split_count, from_page=start_page, to_page=end_page)
                                if ocr_pdf_split: apply_ocr_to_doc(new_part_doc)
                                part_buffer = io.BytesIO()
                                final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                                new_part_doc.save(part_buffer, **final_save_options); part_buffer.seek(0)
                                part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteN{part_number}.pdf"
                                st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                                part_number += 1; new_part_doc.close()
                            if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                            else: st.warning("Não foi possível dividir o PDF.")
                        except Exception as e: st.session_state.error_message = f"Erro ao dividir PDF: {e}"; st.error(st.session_state.error_message)
                        finally:
                            if original_doc_for_split_count: original_doc_for_split_count.close()
                            progress_bar_split_count.empty()
                    st.session_state.processing_split = False
                    st.rerun()

            if st.session_state.split_pdf_parts:
                st.subheader("Baixar Partes do PDF Dividido:")
                if len(st.session_state.split_pdf_parts) > 1:
                    zip_buffer = io.BytesIO()
                    with st.spinner("A preparar ZIP das partes..."):
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                            for part in st.session_state.split_pdf_parts:
                                zip_file.writestr(part["name"], part["data"])
                        zip_buffer.seek(0)
                    st.download_button(label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP", data=zip_buffer, file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip", mime="application/zip", key="download_zip_button_tab_split_v7")
                    st.markdown("---")
                for i, part in enumerate(st.session_state.split_pdf_parts):
                    st.download_button(label=f"Baixar {part['name']}", data=part["data"], file_name=part["name"], mime="application/pdf", key=f"download_part_{i}_button_tab_split_v7")
        
        # --- ABA: EXTRAIR PÁGINAS ---
        with selected_tab[2]: # Corresponde a "Extrair Páginas"
            st.header("Extrair Páginas Específicas")
            extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract_v7")
            optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract_v7")
            ocr_pdf_extract = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_extract_checkbox_tab_extract_v7", help="Requer Tesseract. Pode demorar.")
            
            if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract_v7", disabled=st.session_state.get('processing_extract', False)):
                st.session_state.processing_extract = True
                st.session_state.processed_pdf_bytes_extract = None; st.session_state.error_message = None
                
                doc_original_for_extract = None
                new_extracted_doc = None
                with st.spinner("A extrair páginas... Por favor, aguarde."):
                    try:
                        doc_original_for_extract = fitz.open(stream=doc_cached.write(), filetype="pdf") # Cópia para não modificar o cache
                        pages_to_extract_0_indexed = parse_page_input(extract_pages_str, doc_original_for_extract.page_count)
                        if not pages_to_extract_0_indexed: st.warning("Nenhuma página especificada para extração.")
                        else:
                            new_extracted_doc = fitz.open()
                            # selected_pages espera uma lista de inteiros 0-indexados
                            new_extracted_doc.insert_pdf(doc_original_for_extract, selected_pages=pages_to_extract_0_indexed) 
                            
                            if ocr_pdf_extract: apply_ocr_to_doc(new_extracted_doc)
                            save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            new_extracted_doc.save(pdf_output_buffer, **save_options); pdf_output_buffer.seek(0)
                            st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                            st.success(f"PDF com {len(pages_to_extract_0_indexed)} página(s) extraída(s) pronto!")
                    except Exception as e: st.session_state.error_message = f"Erro ao extrair páginas: {e}"; st.error(st.session_state.error_message)
                    finally: 
                        if doc_original_for_extract: doc_original_for_extract.close()
                        if new_extracted_doc: new_extracted_doc.close()
                st.session_state.processing_extract = False
                st.rerun()
            
            if st.session_state.processed_pdf_bytes_extract:
                download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
                st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract_v7")

        # --- ABA: GERIR PÁGINAS VISUALMENTE ---
        with selected_tab[3]: # Corresponde a "Gerir Páginas Visualmente"
            st.header("Gerir Páginas Visualmente")
            if st.session_state.active_tab_for_preview != "visual_manage" or not st.session_state.page_previews:
                if not st.session_state.page_previews and doc_cached and not st.session_state.generating_previews:
                    st.session_state.generating_previews = True
                    with st.spinner("Gerando pré-visualizações das páginas..."):
                        previews = []
                        total_pages_for_preview = doc_cached.page_count
                        preview_progress = st.progress(0, text="Gerando miniaturas... 0%")
                        for page_num in range(total_pages_for_preview):
                            page = doc_cached.load_page(page_num)
                            pix = page.get_pixmap(dpi=50) 
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            previews.append(img_byte_arr.getvalue())
                            preview_progress.progress(int(((page_num + 1) / total_pages_for_preview) * 100), text=f"Gerando miniatura {page_num+1}/{total_pages_for_preview}")
                        st.session_state.page_previews = previews
                        preview_progress.empty()
                    st.session_state.generating_previews = False
                    st.session_state.active_tab_for_preview = "visual_manage"
                    st.rerun() 
            
            if not st.session_state.page_previews:
                st.info("Clique novamente nesta aba ou carregue um PDF para gerar as pré-visualizações.")
            else:
                st.markdown(f"Total de páginas: {len(st.session_state.page_previews)}. Selecione as páginas abaixo:")
                num_cols_preview = st.sidebar.slider("Colunas para pré-visualização:", 2, 8, 4, key="preview_cols_slider_v7")
                cols = st.columns(num_cols_preview)
                
                for i, img_bytes in enumerate(st.session_state.page_previews):
                    with cols[i % num_cols_preview]:
                        page_key = f"select_page_preview_{i}_v7" 
                        if i not in st.session_state.visual_page_selection:
                            st.session_state.visual_page_selection[i] = False
                        st.image(img_bytes, caption=f"Página {i+1}", width=120)
                        st.session_state.visual_page_selection[i] = st.checkbox("Selecionar", value=st.session_state.visual_page_selection[i], key=page_key)
                
                selected_page_indices = sorted([k for k, v in st.session_state.visual_page_selection.items() if v])
                st.markdown(f"**Páginas selecionadas (0-indexadas):** {selected_page_indices if selected_page_indices else 'Nenhuma'}")

                col_action1, col_action2 = st.columns(2)
                with col_action1:
                    if st.button("Excluir Páginas Selecionadas", key="delete_visual_button_tab_visual_v7", disabled=st.session_state.get('processing_visual_delete', False)):
                        st.session_state.processing_visual_delete = True
                        st.session_state.processed_pdf_bytes_visual = None; st.session_state.error_message = None
                        if not selected_page_indices: st.warning("Nenhuma página selecionada para exclusão.")
                        else:
                            with st.spinner("A excluir páginas selecionadas..."):
                                doc_to_modify_vis = None
                                try:
                                    doc_to_modify_vis = fitz.open(stream=doc_cached.write(), filetype="pdf")
                                    if len(selected_page_indices) >= doc_to_modify_vis.page_count: st.error("Não é permitido excluir todas as páginas.")
                                    else:
                                        doc_to_modify_vis.delete_pages(selected_page_indices)
                                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                                        pdf_output_buffer = io.BytesIO()
                                        doc_to_modify_vis.save(pdf_output_buffer, **save_options)
                                        st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                        st.success(f"{len(selected_page_indices)} página(s) excluída(s)!")
                                        st.session_state.visual_page_selection = {} # Limpa seleção
                                except Exception as e: st.error(f"Erro ao excluir páginas: {e}")
                                finally: 
                                    if doc_to_modify_vis: doc_to_modify_vis.close()
                        st.session_state.processing_visual_delete = False
                        st.rerun()

                with col_action2:
                    if st.button("Extrair Páginas Selecionadas", key="extract_visual_button_tab_visual_v7", disabled=st.session_state.get('processing_visual_extract', False)):
                        st.session_state.processing_visual_extract = True
                        st.session_state.processed_pdf_bytes_visual = None; st.session_state.error_message = None
                        if not selected_page_indices: st.warning("Nenhuma página selecionada para extração.")
                        else:
                            with st.spinner("A extrair páginas selecionadas..."):
                                doc_original_vis = None; new_doc_vis = None
                                try:
                                    doc_original_vis = fitz.open(stream=doc_cached.write(), filetype="pdf")
                                    new_doc_vis = fitz.open()
                                    new_doc_vis.insert_pdf(doc_original_vis, selected_pages=selected_page_indices)
                                    save_options = {"garbage": 4, "deflate": True, "clean": True}
                                    pdf_output_buffer = io.BytesIO()
                                    new_doc_vis.save(pdf_output_buffer, **save_options)
                                    st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                    st.success(f"{len(selected_page_indices)} página(s) extraída(s)!")
                                    st.session_state.visual_page_selection = {} # Limpa seleção
                                except Exception as e: st.error(f"Erro ao extrair páginas: {e}")
                                finally:
                                    if doc_original_vis: doc_original_vis.close()
                                    if new_doc_vis: new_doc_vis.close()
                        st.session_state.processing_visual_extract = False
                        st.rerun()
                
                if st.session_state.processed_pdf_bytes_visual:
                    action_type_visual = "excluido_vis" if st.session_state.get('delete_visual_button_tab_visual_v7') else "extraido_vis"
                    download_filename_visual = f"{os.path.splitext(st.session_state.pdf_name)[0]}_{action_type_visual}.pdf"
                    st.download_button(
                        label=f"Baixar PDF ({action_type_visual.replace('_', ' ')})", 
                        data=st.session_state.processed_pdf_bytes_visual,
                        file_name=download_filename_visual, mime="application/pdf", key="download_visual_button_tab_visual_v7"
                    )

        # --- ABA: APLICAR OCR ---
        with selected_tab[4]: # Corresponde a "Aplicar OCR"
            st.header("Aplicar OCR ao PDF Inteiro")
            st.markdown("Esta funcionalidade tentará tornar o texto do seu PDF pesquisável. O PDF original não será alterado; um novo PDF com OCR será gerado para download.")
            
            if not OCR_AVAILABLE:
                st.error("O Tesseract OCR não foi detectado neste ambiente. A funcionalidade de OCR está desabilitada. Verifique as instruções na barra lateral.")
            
            optimize_ocr_output = st.checkbox("Otimizar PDF com OCR ao salvar", value=True, key="optimize_ocr_output_checkbox_v7")

            if st.button("Aplicar OCR e Preparar Download", key="apply_ocr_button_v7", disabled=st.session_state.get('processing_ocr', False) or not OCR_AVAILABLE):
                st.session_state.processing_ocr = True
                st.session_state.processed_pdf_bytes_ocr = None; st.session_state.error_message = None
                
                doc_for_ocr = None
                with st.spinner("Aplicando OCR... Este processo pode ser demorado."):
                    try:
                        doc_for_ocr = fitz.open(stream=doc_cached.write(), filetype="pdf")
                        ocr_applied_successfully = apply_ocr_to_doc(doc_for_ocr)
                        
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_ocr_output: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        
                        pdf_output_buffer = io.BytesIO()
                        doc_for_ocr.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_ocr = pdf_output_buffer.getvalue()
                        if ocr_applied_successfully:
                            st.success("PDF com OCR aplicado pronto para download!")
                        elif ocr_applied_successfully is False and not st.session_state.error_message:
                             st.info("PDF salvo. O OCR pode não ter sido aplicado (ex: já era pesquisável ou Tesseract não funcional).")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao salvar PDF após tentativa de OCR: {e}"; st.error(st.session_state.error_message)
                    finally:
                        if doc_for_ocr: doc_for_ocr.close()
                st.session_state.processing_ocr = False
                st.rerun()

            if st.session_state.processed_pdf_bytes_ocr:
                download_filename_ocr = f"{os.path.splitext(st.session_state.pdf_name)[0]}_ocr.pdf"
                st.download_button(label="Baixar PDF com OCR", data=st.session_state.processed_pdf_bytes_ocr, file_name=download_filename_ocr, mime="application/pdf", key="download_ocr_button_v7")

# Exibir mensagem de erro global
if st.session_state.error_message and not any([st.session_state.processed_pdf_bytes_remove, 
                                                st.session_state.processed_pdf_bytes_extract, 
                                                st.session_state.processed_pdf_bytes_visual,
                                                st.session_state.processed_pdf_bytes_ocr,
                                                st.session_state.split_pdf_parts]):
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover, dividir, extrair e aplicar OCR em arquivos PDF. "
    "Desenvolvido com Streamlit e PyMuPDF."
)
if not OCR_AVAILABLE:
    st.sidebar.error("OCR INDISPONÍVEL: Tesseract OCR não foi detectado no ambiente do servidor. Para ativar, adicione `tesseract-ocr` e `tesseract-ocr-por` ao seu `packages.txt` no Streamlit Cloud.")

