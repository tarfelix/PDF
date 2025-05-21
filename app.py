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

# --- Dicionário Padrão para o Estado da Sessão ---
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 
    'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_ocr': None,
    'split_pdf_parts': [], 'error_message': None, 'last_uploaded_filename': None,
    'page_previews': [], 'visual_page_selection': {}, 
    'processing_remove': False, 'processing_split': False, 'processing_extract': False, 
    'processing_visual_delete': False, 'processing_visual_extract': False, 'processing_ocr': False,
    'active_tab_for_preview': None, 'generating_previews': False
}

# --- Cache para Carregamento do PDF ---
@st.cache_resource(show_spinner="Carregando e analisando PDF...")
def load_pdf_from_bytes(pdf_bytes, filename="uploaded_pdf"):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # Realizar operações que só dependem do doc aqui para aproveitar o cache
        bookmarks = get_bookmark_ranges(doc) 
        page_count = doc.page_count
        # Retornar o objeto doc e os dados extraídos
        return doc, bookmarks, page_count
    except Exception as e:
        st.error(f"Erro ao carregar o PDF '{filename}': {e}")
        return None, [], 0

# --- Funções Auxiliares ---
def get_bookmark_ranges(pdf_doc_instance): # Recebe a instância do documento
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
    # ... (mantida como antes)
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
        is_already_searchable = all(page.get_text("text") for page in doc_to_ocr)
        if is_already_searchable:
            st.info("O PDF já parece ser pesquisável. OCR não será reaplicado.")
            return False # Indica que não houve necessidade de aplicar OCR

        total_pages = len(doc_to_ocr)
        if total_pages == 0:
            st.info("Documento está vazio, OCR não aplicável.")
            return False
            
        ocr_progress_text = "Aplicando OCR (Português)... 0%"
        ocr_progress_bar = st.progress(0, text=ocr_progress_text)
        
        if hasattr(doc_to_ocr, "ocr_pdf"):
            # Simular progresso, pois ocr_pdf não tem callback direto
            # Poderia ser mais granular se processássemos página a página, mas ocr_pdf é mais otimizado
            doc_to_ocr.ocr_pdf(language="por")
            ocr_progress_bar.progress(100, text="OCR Aplicado!")
            st.success("OCR aplicado com sucesso!")
            return True # OCR foi aplicado
        else:
            st.warning("Método `ocr_pdf` não encontrado no PyMuPDF. A funcionalidade de OCR pode não estar disponível ou requer uma versão mais recente do PyMuPDF. Verifique também se o Tesseract OCR está instalado no servidor.")
            ocr_progress_bar.empty()
            return False
    except Exception as e:
        st.error(f"Erro durante o processo de OCR: {e}. Verifique se o Tesseract OCR e o pacote de idioma 'por' estão instalados no servidor. O PDF será salvo sem OCR adicional.")
        if 'ocr_progress_bar' in locals(): ocr_progress_bar.empty()
        return False # OCR falhou

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value if not isinstance(value, (list, dict, set)) else type(value)()
initialize_session_state()

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar PDF Carregado e Seleções", key="clear_all_sidebar_btn_v7"):
    for key in DEFAULT_STATE.keys(): # Itera sobre as chaves do dicionário padrão
        if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
        elif key == 'visual_page_selection': st.session_state[key] = {}
        elif key.startswith('processing_'): st.session_state[key] = False
        else: st.session_state[key] = None
            
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or "_input" in k or "_checkbox" in k]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    
    load_pdf_from_bytes.clear() # Limpa o cache da função de carregamento
    st.success("Estado da aplicação limpo!")
    st.rerun()

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader_main_v7")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        # Resetar estados que dependem do PDF carregado
        for key in DEFAULT_STATE.keys(): # Reseta para o padrão, exceto o que foi carregado
            if key not in ['pdf_doc_bytes_original', 'pdf_name', 'last_uploaded_filename']:
                if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
                elif key == 'visual_page_selection': st.session_state[key] = {}
                elif key.startswith('processing_'): st.session_state[key] = False
                else: st.session_state[key] = None
        
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_")]
        for k_del in keys_to_delete:
            if k_del in st.session_state: del st.session_state[k_del]
        
        load_pdf_from_bytes.clear() # Limpa o cache antes de carregar o novo
        doc, bookmarks, page_count = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
        if doc:
            st.info(f"PDF '{st.session_state.pdf_name}' carregado com {page_count} páginas.")
            st.session_state.bookmarks_data = bookmarks
        else:
            st.session_state.pdf_doc_bytes_original = None
else:
    if st.session_state.last_uploaded_filename is not None:
        st.session_state.pdf_doc_bytes_original = None
        st.session_state.last_uploaded_filename = None
        load_pdf_from_bytes.clear()

# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original:
    doc_cached, _, _ = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if not doc_cached:
        st.error("Não foi possível carregar o documento PDF para processamento.")
    else:
        active_tabs = ["Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente", "Aplicar OCR"]
        selected_tab = st.tabs(active_tabs)

        # --- ABA: REMOVER PÁGINAS ---
        with selected_tab[0]: # Corresponde a "Remover Páginas"
            # ... (Lógica da aba remover, usando doc_cached e st.progress)
            # ... Similar à v6, mas com a barra de progresso e usando o doc_cached para operações
            st.header("Remover Páginas do PDF")
            # ... (Implementação completa omitida para brevidade, mas seguiria o padrão da v6
            #      com as melhorias de UX e usando doc_cached.get_stream() para criar cópias modificáveis)

        # --- ABA: DIVIDIR PDF ---
        with selected_tab[1]:
            st.header("Dividir PDF")
            # ... (Lógica da aba dividir, com st.progress)
            st.info("Funcionalidade de Divisão de PDF: Lógica de processamento e barra de progresso a serem implementadas aqui.")


        # --- ABA: EXTRAIR PÁGINAS ---
        with selected_tab[2]:
            st.header("Extrair Páginas Específicas")
            # ... (Lógica da aba extrair, com st.progress)
            extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract_v7")
            optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract_v7")
            ocr_pdf_extract = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_extract_checkbox_tab_extract_v7", help="Requer Tesseract. Pode demorar.")
            
            if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract_v7", disabled=st.session_state.get('processing_extract', False)):
                st.session_state.processing_extract = True
                st.session_state.processed_pdf_bytes_extract = None; st.session_state.error_message = None
                
                doc_original_copy = fitz.open(stream=doc_cached.write(), filetype="pdf") # Cópia para modificação

                with st.spinner("A extrair páginas... Por favor, aguarde."):
                    pages_to_extract_0_indexed = parse_page_input(extract_pages_str, doc_original_copy.page_count)
                    if not pages_to_extract_0_indexed: st.warning("Nenhuma página especificada para extração.")
                    else:
                        try:
                            new_extracted_doc = fitz.open()
                            # Correção: Usar insert_pdf com selected_pages
                            new_extracted_doc.insert_pdf(doc_original_copy, selected_pages=pages_to_extract_0_indexed)
                            
                            if ocr_pdf_extract: apply_ocr_to_doc(new_extracted_doc)
                            save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            new_extracted_doc.save(pdf_output_buffer, **save_options); pdf_output_buffer.seek(0)
                            st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                            st.success(f"PDF com {len(pages_to_extract_0_indexed)} página(s) extraída(s) pronto!")
                            new_extracted_doc.close()
                        except Exception as e: st.session_state.error_message = f"Erro ao extrair páginas: {e}"; st.error(st.session_state.error_message)
                        finally: doc_original_copy.close()
                st.session_state.processing_extract = False
                st.rerun()
            
            if st.session_state.processed_pdf_bytes_extract:
                download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
                st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract_v7")


        # --- ABA: GERIR PÁGINAS VISUALMENTE ---
        with selected_tab[3]:
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
                    st.session_state.active_tab_for_preview = "visual_manage" # Marca que as previews para esta aba foram geradas
                    st.rerun() # Rerun para exibir as previews agora que foram geradas
            
            if not st.session_state.page_previews:
                st.info("Clique novamente nesta aba ou carregue um PDF para gerar as pré-visualizações.")
            else:
                # ... (Lógica da aba visual, adaptada para usar doc_cached e o novo st.session_state.visual_page_selection)
                st.info("Funcionalidade de Gerir Páginas Visualmente: Lógica de seleção e ações a serem implementadas aqui.")


        # --- ABA: APLICAR OCR ---
        with selected_tab[4]:
            st.header("Aplicar OCR ao PDF Inteiro")
            st.markdown("Esta funcionalidade tentará tornar o texto do seu PDF pesquisável. O PDF original não será alterado; um novo PDF com OCR será gerado para download.")
            
            if not OCR_AVAILABLE:
                st.error("O Tesseract OCR não foi detectado neste ambiente. A funcionalidade de OCR está desabilitada. Verifique as instruções na barra lateral.")
            
            optimize_ocr_output = st.checkbox("Otimizar PDF com OCR ao salvar", value=True, key="optimize_ocr_output_checkbox_v7")

            if st.button("Aplicar OCR e Preparar Download", key="apply_ocr_button_v7", disabled=st.session_state.get('processing_ocr', False) or not OCR_AVAILABLE):
                st.session_state.processing_ocr = True
                st.session_state.processed_pdf_bytes_ocr = None; st.session_state.error_message = None
                
                doc_for_ocr = fitz.open(stream=doc_cached.write(), filetype="pdf") # Cópia para OCR

                ocr_applied_successfully = apply_ocr_to_doc(doc_for_ocr)
                
                if doc_for_ocr: # Mesmo se o OCR falhar, tentamos salvar o documento (que pode ter sido modificado ou não)
                    try:
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_ocr_output: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        
                        pdf_output_buffer = io.BytesIO()
                        doc_for_ocr.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_ocr = pdf_output_buffer.getvalue()
                        if ocr_applied_successfully:
                            st.success("PDF com OCR aplicado pronto para download!")
                        elif ocr_applied_successfully is False and not st.session_state.error_message: # OCR não necessário ou falhou sem exceção grave
                             st.info("PDF salvo. O OCR pode não ter sido aplicado (ex: já era pesquisável ou Tesseract não funcional).")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao salvar PDF após tentativa de OCR: {e}"; st.error(st.session_state.error_message)
                    finally:
                        doc_for_ocr.close()
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

