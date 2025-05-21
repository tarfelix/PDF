import streamlit as st
import fitz  # PyMuPDF
import os
import io
import zipfile
from PIL import Image # Para manipular imagens para pré-visualização

# Tenta importar pymupdf_tesseract para OCR.
try:
    import pymupdf_tesseract # type: ignore # Suprime o aviso de importação não resolvida se não estiver instalado localmente
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pymupdf_tesseract = None 
    print("pymupdf_tesseract não encontrado. Funcionalidade de OCR estará desabilitada.")


# Configuração da página
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Pro (PT-BR)")

st.title("✂️ Editor e Divisor de PDF Pro")
st.markdown("""
    **Funcionalidades:**
    1.  **Remover Páginas:** Exclua seções com base em marcadores (bookmarks) ou números de página específicos.
    2.  **Dividir PDF:**
        * Por tamanho máximo de arquivo (MB).
        * A cada N páginas.
    3.  **Extrair Páginas:** Crie um novo PDF contendo apenas as páginas selecionadas.
    4.  **Gerir Páginas Visualmente:** Pré-visualize e selecione páginas para exclusão ou extração.
    5.  **Tornar Pesquisável (OCR):** Converta PDFs baseados em imagem em PDFs pesquisáveis (requer configuração do Tesseract no ambiente).
""")

# --- Funções Auxiliares ---
def get_bookmark_ranges(pdf_doc):
    bookmarks_data = []
    if not pdf_doc: return bookmarks_data
    try:
        toc = pdf_doc.get_toc(simple=False)
    except Exception as e:
        st.error(f"Erro ao obter marcadores: {e}"); return bookmarks_data
    if not toc: return bookmarks_data
    num_total_pages_doc = pdf_doc.page_count
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

def apply_ocr_if_needed(doc_to_save, ocr_flag):
    if not ocr_flag:
        return False 

    if not OCR_AVAILABLE or pymupdf_tesseract is None:
        st.warning("Funcionalidade de OCR não está disponível (pymupdf-tesseract não importado ou Tesseract não configurado). O PDF será salvo sem OCR.")
        return False

    try:
        # Verifica se o documento já é pesquisável para evitar reprocessamento
        is_already_searchable = True
        if len(doc_to_save) == 0: # Documento vazio
             st.info("Documento está vazio, OCR não aplicável.")
             return False

        for page_num in range(len(doc_to_save)):
            page = doc_to_save.load_page(page_num)
            if not page.get_text("text"): 
                is_already_searchable = False
                break
        
        if is_already_searchable:
            st.info("O PDF já parece ser pesquisável. OCR não será reaplicado.")
            return False

        st.write("Aplicando OCR (Português)... Este processo pode demorar.")
        # Tenta usar o método ez_ocr ou um similar fornecido por pymupdf_tesseract
        if hasattr(doc_to_save, "ez_ocr"): 
             doc_to_save.ez_ocr(language="por") 
        elif hasattr(pymupdf_tesseract, "apply_ocr_on_doc"): 
             pymupdf_tesseract.apply_ocr_on_doc(doc_to_save, language="por")
        else: # Fallback se os métodos específicos não existirem
            # PyMuPDF >= 1.19.0 tem ocr_pdf
            if hasattr(doc_to_save, "ocr_pdf"):
                 doc_to_save.ocr_pdf(language="por")
            else:
                st.warning("Método de OCR direto do PyMuPDF (`ez_ocr` ou `ocr_pdf`) não encontrado. Verifique a instalação e versão do `PyMuPDF` e `pymupdf-tesseract`.")
                return False
        st.success("OCR aplicado com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro durante o processo de OCR: {e}. O PDF será salvo sem OCR adicional.")
        return False

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    defaults = {
        'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
        'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 'processed_pdf_bytes_visual': None,
        'split_pdf_parts': [], 'error_message': None, 'last_uploaded_filename': None,
        'page_previews': [], 'selected_pages_for_visual_management': set(),
        'processing_remove': False, 'processing_split': False, 'processing_extract': False, 'processing_visual': False
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

initialize_session_state()

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar PDF Carregado e Seleções", key="clear_all_sidebar_btn"):
    keys_to_reset = [
        'pdf_doc_bytes_original', 'pdf_name', 'bookmarks_data', 
        'processed_pdf_bytes_remove', 'processed_pdf_bytes_extract', 'processed_pdf_bytes_visual',
        'split_pdf_parts', 'error_message', 'last_uploaded_filename', 'page_previews', 
        'selected_pages_for_visual_management',
        'processing_remove', 'processing_split', 'processing_extract', 'processing_visual'
    ]
    for key in keys_to_reset:
        if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
        elif key == 'selected_pages_for_visual_management': st.session_state[key] = set()
        elif key.startswith('processing_'): st.session_state[key] = False
        else: st.session_state[key] = None
            
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or k.startswith("select_page_preview_") or "_input" in k or "_checkbox" in k]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    st.success("Estado da aplicação limpo!")
    st.rerun()

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader_main_v5")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        st.session_state.bookmarks_data = []
        st.session_state.processed_pdf_bytes_remove = None
        st.session_state.processed_pdf_bytes_extract = None
        st.session_state.processed_pdf_bytes_visual = None
        st.session_state.split_pdf_parts = []
        st.session_state.error_message = None
        st.session_state.page_previews = []
        st.session_state.selected_pages_for_visual_management = set()
        
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_") or k.startswith("select_page_preview_")]
        for k_del in keys_to_delete:
            if k_del in st.session_state: del st.session_state[k_del]
        
        with st.spinner("Analisando PDF e gerando pré-visualizações..."):
            try:
                with fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf") as temp_doc:
                    st.info(f"PDF '{st.session_state.pdf_name}' carregado com {temp_doc.page_count} páginas.")
                    st.session_state.bookmarks_data = get_bookmark_ranges(temp_doc)
                    previews = []
                    for page_num in range(temp_doc.page_count):
                        page = temp_doc.load_page(page_num)
                        pix = page.get_pixmap(dpi=72) 
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='PNG')
                        previews.append(img_byte_arr.getvalue())
                    st.session_state.page_previews = previews
            except Exception as e:
                st.session_state.error_message = f"Erro ao abrir ou processar o PDF: {e}"
                st.error(st.session_state.error_message)
                st.session_state.pdf_doc_bytes_original = None 
else:
    if st.session_state.last_uploaded_filename is not None:
        st.session_state.pdf_doc_bytes_original = None
        st.session_state.last_uploaded_filename = None

# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original:
    tab_remove, tab_split, tab_extract, tab_visual_manage = st.tabs([
        "Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente"
    ])

    # --- ABA: REMOVER PÁGINAS ---
    with tab_remove:
        st.header("Remover Páginas do PDF")
        with st.expander("Excluir por Marcadores", expanded=True):
            if st.session_state.bookmarks_data:
                st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
                with st.container(height=300):
                    for bm in st.session_state.bookmarks_data:
                        checkbox_key = f"delete_bookmark_{bm['id']}_tab_remove"
                        if checkbox_key not in st.session_state: st.session_state[checkbox_key] = False
                        st.checkbox(label=bm['display_text'], value=st.session_state[checkbox_key], key=checkbox_key)
            else:
                st.info("Nenhum marcador encontrado neste PDF para seleção.")

        with st.expander("Excluir por Números de Página", expanded=True):
            direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove")
        
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox_tab_remove")
        ocr_pdf_remove = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_remove_checkbox_tab_remove", help="Requer Tesseract OCR e pacote de idioma português configurados no ambiente do servidor. Pode demorar e aumentar o tamanho do arquivo se já for pesquisável.")
        if ocr_pdf_remove and not OCR_AVAILABLE:
            st.warning("A biblioteca `pymupdf-tesseract` não foi encontrada ou o Tesseract não está configurado. A funcionalidade de OCR não estará disponível.")

        if st.button("Processar Remoção de Páginas", key="process_remove_button_tab_remove", disabled=st.session_state.get('processing_remove', False)):
            st.session_state.processing_remove = True
            st.session_state.processed_pdf_bytes_remove = None; st.session_state.error_message = None
            with st.spinner("A processar remoção de páginas... Por favor, aguarde."):
                doc_to_modify = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                selected_bookmark_pages_to_delete = set()
                if st.session_state.bookmarks_data:
                    for bm in st.session_state.bookmarks_data:
                        if st.session_state.get(f"delete_bookmark_{bm['id']}_tab_remove", False):
                            for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                                selected_bookmark_pages_to_delete.add(page_num)
                direct_pages_to_delete_list = parse_page_input(direct_pages_str_tab_remove, doc_to_modify.page_count)
                all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

                if not all_pages_to_delete_0_indexed: st.warning("Nenhuma página selecionada para exclusão.")
                elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                    st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas do PDF, pois resultaria num arquivo vazio."; st.error(st.session_state.error_message)
                else:
                    try:
                        doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                        if ocr_pdf_remove: apply_ocr_if_needed(doc_to_modify, True) # Passa o doc e a flag
                        
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_remove: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        pdf_output_buffer = io.BytesIO()
                        doc_to_modify.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_remove = pdf_output_buffer.getvalue()
                        st.success(f"PDF processado! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                    except Exception as e: st.session_state.error_message = f"Erro ao remover páginas: {e}"; st.error(st.session_state.error_message)
                    finally: doc_to_modify.close()
            st.session_state.processing_remove = False
            st.rerun() # Para atualizar o estado do botão de download

        if st.session_state.processed_pdf_bytes_remove:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_editado.pdf"
            st.download_button(label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button_tab_remove")

    # --- ABA: DIVIDIR PDF ---
    with tab_split:
        st.header("Dividir PDF")
        split_method = st.radio("Método de Divisão:", ("Por Tamanho Máximo (MB)", "A Cada N Páginas"), key="split_method_radio_tab_split")
        optimize_pdf_split = st.checkbox("Otimizar partes divididas", value=True, key="optimize_pdf_split_checkbox_tab_split")
        ocr_pdf_split = st.checkbox("Tornar partes pesquisáveis (OCR - Português)", value=False, key="ocr_pdf_split_checkbox_tab_split", help="Requer Tesseract. Pode demorar e aumentar o tamanho.")
        if ocr_pdf_split and not OCR_AVAILABLE: st.warning("OCR desabilitado: `pymupdf-tesseract` não encontrado ou Tesseract não configurado.")

        if split_method == "Por Tamanho Máximo (MB)":
            max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=5.0, step=0.1, format="%.1f", key="max_size_mb_input_tab_split")
            if st.button("Dividir por Tamanho", key="split_by_size_button_tab_split", disabled=st.session_state.get('processing_split', False)):
                st.session_state.processing_split = True
                st.session_state.split_pdf_parts = [] ; st.session_state.error_message = None
                with st.spinner("A dividir PDF por tamanho... Por favor, aguarde."):
                    max_size_bytes = int(max_size_mb * 1024 * 1024)
                    try:
                        original_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                        total_pages_original = original_doc.page_count; current_page_index = 0; part_number = 1
                        while current_page_index < total_pages_original:
                            new_part_doc = fitz.open(); pages_in_current_part = 0
                            while current_page_index < total_pages_original:
                                temp_doc_for_size_check = fitz.open()
                                if pages_in_current_part > 0: temp_doc_for_size_check.insert_pdf(new_part_doc)
                                temp_doc_for_size_check.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                                temp_buffer = io.BytesIO()
                                save_options_check = {"garbage": 0, "deflate": optimize_pdf_split}
                                if optimize_pdf_split: save_options_check.update({"deflate_images": True, "deflate_fonts": True})
                                temp_doc_for_size_check.save(temp_buffer, **save_options_check)
                                estimated_size = len(temp_buffer.getvalue()); temp_doc_for_size_check.close(); temp_buffer.close()
                                if pages_in_current_part > 0 and estimated_size > max_size_bytes: break 
                                new_part_doc.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                                current_page_index += 1; pages_in_current_part += 1
                                if estimated_size > max_size_bytes and pages_in_current_part == 1:
                                    st.warning(f"Página {current_page_index} excede o limite. Será parte separada."); break
                            if pages_in_current_part > 0:
                                if ocr_pdf_split: apply_ocr_if_needed(new_part_doc, True)
                                part_buffer = io.BytesIO()
                                final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                                if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                                new_part_doc.save(part_buffer, **final_save_options); part_buffer.seek(0)
                                part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteT{part_number}.pdf"
                                st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                                part_number += 1
                            new_part_doc.close()
                        original_doc.close()
                        if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                        else: st.warning("Não foi possível dividir o PDF.")
                    except Exception as e: st.session_state.error_message = f"Erro ao dividir PDF: {e}"; st.error(st.session_state.error_message)
                st.session_state.processing_split = False
                st.rerun()

        elif split_method == "A Cada N Páginas":
            pages_per_split = st.number_input("Número de páginas por parte:", min_value=1, value=10, step=1, key="pages_per_split_input_tab_split")
            if st.button("Dividir por Número de Páginas", key="split_by_count_button_tab_split", disabled=st.session_state.get('processing_split', False)):
                st.session_state.processing_split = True
                st.session_state.split_pdf_parts = []; st.session_state.error_message = None
                with st.spinner("A dividir PDF por número de páginas... Por favor, aguarde."):
                    try:
                        original_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                        total_pages_original = original_doc.page_count; part_number = 1
                        for i in range(0, total_pages_original, pages_per_split):
                            new_part_doc = fitz.open()
                            start_page = i; end_page = min(i + pages_per_split - 1, total_pages_original - 1)
                            new_part_doc.insert_pdf(original_doc, from_page=start_page, to_page=end_page)
                            if ocr_pdf_split: apply_ocr_if_needed(new_part_doc, True)
                            part_buffer = io.BytesIO()
                            final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_split: final_save_options.update({"deflate_images": True, "deflate_fonts": True})
                            new_part_doc.save(part_buffer, **final_save_options); part_buffer.seek(0)
                            part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parteN{part_number}.pdf"
                            st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                            part_number += 1; new_part_doc.close()
                        original_doc.close()
                        if st.session_state.split_pdf_parts: st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                        else: st.warning("Não foi possível dividir o PDF.")
                    except Exception as e: st.session_state.error_message = f"Erro ao dividir PDF: {e}"; st.error(st.session_state.error_message)
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
                st.download_button(label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP", data=zip_buffer, file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip", mime="application/zip", key="download_zip_button_tab_split")
                st.markdown("---")
            for i, part in enumerate(st.session_state.split_pdf_parts):
                st.download_button(label=f"Baixar {part['name']}", data=part["data"], file_name=part["name"], mime="application/pdf", key=f"download_part_{i}_button_tab_split")
    
    # --- ABA: EXTRAIR PÁGINAS ---
    with tab_extract:
        st.header("Extrair Páginas Específicas")
        extract_pages_str = st.text_input("Páginas a extrair (ex: 1, 3-5, 8):", key="extract_pages_input_tab_extract")
        optimize_pdf_extract = st.checkbox("Otimizar PDF extraído", value=True, key="optimize_pdf_extract_checkbox_tab_extract")
        ocr_pdf_extract = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_extract_checkbox_tab_extract", help="Requer Tesseract. Pode demorar.")
        if ocr_pdf_extract and not OCR_AVAILABLE: st.warning("OCR desabilitado: `pymupdf-tesseract` não encontrado ou Tesseract não configurado.")

        if st.button("Processar Extração de Páginas", key="process_extract_button_tab_extract", disabled=st.session_state.get('processing_extract', False)):
            st.session_state.processing_extract = True
            st.session_state.processed_pdf_bytes_extract = None; st.session_state.error_message = None
            with st.spinner("A extrair páginas... Por favor, aguarde."):
                doc_temp_extract = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                pages_to_extract_0_indexed = parse_page_input(extract_pages_str, doc_temp_extract.page_count)
                if not pages_to_extract_0_indexed: st.warning("Nenhuma página especificada para extração.")
                else:
                    try:
                        new_extracted_doc = fitz.open()
                        new_extracted_doc.insert_pdf(doc_temp_extract, from_page=0, to_page=doc_temp_extract.page_count-1, toc=False, annots=True, links=True, selected_pages=pages_to_extract_0_indexed) # selected_pages é o novo nome
                        
                        if ocr_pdf_extract: apply_ocr_if_needed(new_extracted_doc, True)
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_pdf_extract: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        pdf_output_buffer = io.BytesIO()
                        new_extracted_doc.save(pdf_output_buffer, **save_options); pdf_output_buffer.seek(0)
                        st.session_state.processed_pdf_bytes_extract = pdf_output_buffer.getvalue()
                        st.success(f"PDF com {len(pages_to_extract_0_indexed)} página(s) extraída(s) pronto!")
                        new_extracted_doc.close()
                    except Exception as e: st.session_state.error_message = f"Erro ao extrair páginas: {e}"; st.error(st.session_state.error_message)
                    finally: doc_temp_extract.close()
            st.session_state.processing_extract = False
            st.rerun()
        
        if st.session_state.processed_pdf_bytes_extract:
            download_filename_extract = f"{os.path.splitext(st.session_state.pdf_name)[0]}_extraido.pdf"
            st.download_button(label="Baixar PDF Extraído", data=st.session_state.processed_pdf_bytes_extract, file_name=download_filename_extract, mime="application/pdf", key="download_extract_button_tab_extract")

    # --- ABA: GERIR PÁGINAS VISUALMENTE ---
    with tab_visual_manage:
        st.header("Gerir Páginas Visualmente")
        if not st.session_state.page_previews:
            st.info("Carregue um PDF para ver as pré-visualizações das páginas aqui.")
        else:
            st.markdown(f"Total de páginas: {len(st.session_state.page_previews)}. Selecione as páginas abaixo:")
            cols = st.columns(st.sidebar.slider("Colunas para pré-visualização:", 2, 6, 4, key="preview_cols_slider"))
            
            for i, img_bytes in enumerate(st.session_state.page_previews):
                with cols[i % len(cols)]:
                    page_key = f"select_page_preview_{i}"
                    if page_key not in st.session_state: st.session_state[page_key] = False
                    st.image(img_bytes, caption=f"Página {i+1}", width=150)
                    is_selected = st.checkbox("Selecionar", key=page_key, value=st.session_state[page_key])
                    if is_selected: st.session_state.selected_pages_for_visual_management.add(i)
                    elif i in st.session_state.selected_pages_for_visual_management:
                        st.session_state.selected_pages_for_visual_management.remove(i)
            
            st.markdown(f"**Páginas selecionadas (0-indexadas):** {sorted(list(st.session_state.selected_pages_for_visual_management)) if st.session_state.selected_pages_for_visual_management else 'Nenhuma'}")

            col_action1, col_action2 = st.columns(2)
            with col_action1:
                if st.button("Excluir Páginas Selecionadas", key="delete_visual_button", disabled=st.session_state.get('processing_visual', False)):
                    st.session_state.processing_visual = True
                    st.session_state.processed_pdf_bytes_visual = None; st.session_state.error_message = None
                    if not st.session_state.selected_pages_for_visual_management: st.warning("Nenhuma página selecionada para exclusão.")
                    else:
                        with st.spinner("A excluir páginas selecionadas..."):
                            try:
                                doc_to_modify = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                                pages_to_delete = sorted(list(st.session_state.selected_pages_for_visual_management))
                                if len(pages_to_delete) >= doc_to_modify.page_count: st.error("Não é permitido excluir todas as páginas.")
                                else:
                                    doc_to_modify.delete_pages(pages_to_delete)
                                    save_options = {"garbage": 4, "deflate": True, "clean": True}
                                    pdf_output_buffer = io.BytesIO()
                                    doc_to_modify.save(pdf_output_buffer, **save_options)
                                    st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                    st.success(f"{len(pages_to_delete)} página(s) excluída(s)!")
                                    st.session_state.selected_pages_for_visual_management = set() # Limpa seleção
                                    for i_reset in range(len(st.session_state.page_previews)): st.session_state[f"select_page_preview_{i_reset}"] = False
                            except Exception as e: st.error(f"Erro ao excluir páginas: {e}")
                            finally: 
                                if 'doc_to_modify' in locals() and not doc_to_modify.is_closed: doc_to_modify.close()
                    st.session_state.processing_visual = False
                    st.rerun()

            with col_action2:
                if st.button("Extrair Páginas Selecionadas", key="extract_visual_button", disabled=st.session_state.get('processing_visual', False)):
                    st.session_state.processing_visual = True
                    st.session_state.processed_pdf_bytes_visual = None; st.session_state.error_message = None
                    if not st.session_state.selected_pages_for_visual_management: st.warning("Nenhuma página selecionada para extração.")
                    else:
                        with st.spinner("A extrair páginas selecionadas..."):
                            try:
                                doc_original = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                                new_doc = fitz.open()
                                pages_to_extract = sorted(list(st.session_state.selected_pages_for_visual_management))
                                new_doc.insert_pdf(doc_original, from_page=0, to_page=doc_original.page_count-1, toc=False, annots=True, links=True, selected_pages=pages_to_extract)
                                save_options = {"garbage": 4, "deflate": True, "clean": True}
                                pdf_output_buffer = io.BytesIO()
                                new_doc.save(pdf_output_buffer, **save_options)
                                st.session_state.processed_pdf_bytes_visual = pdf_output_buffer.getvalue()
                                st.success(f"{len(pages_to_extract)} página(s) extraída(s)!")
                                st.session_state.selected_pages_for_visual_management = set() # Limpa seleção
                                for i_reset in range(len(st.session_state.page_previews)): st.session_state[f"select_page_preview_{i_reset}"] = False
                            except Exception as e: st.error(f"Erro ao extrair páginas: {e}")
                            finally:
                                if 'doc_original' in locals() and not doc_original.is_closed: doc_original.close()
                                if 'new_doc' in locals() and not new_doc.is_closed: new_doc.close()
                    st.session_state.processing_visual = False
                    st.rerun()
            
            if st.session_state.processed_pdf_bytes_visual:
                action_type_visual = "excluido_vis" if 'delete_visual_button' in st.session_state and st.session_state.delete_visual_button else "extraido_vis"
                download_filename_visual = f"{os.path.splitext(st.session_state.pdf_name)[0]}_{action_type_visual}.pdf"
                st.download_button(
                    label=f"Baixar PDF ({action_type_visual.replace('_', ' ')})", 
                    data=st.session_state.processed_pdf_bytes_visual,
                    file_name=download_filename_visual, mime="application/pdf", key="download_visual_button_tab_visual"
                )

# Exibir mensagem de erro global, se houver
if st.session_state.error_message and not st.session_state.processed_pdf_bytes_remove and \
   not st.session_state.processed_pdf_bytes_extract and not st.session_state.processed_pdf_bytes_visual and \
   not st.session_state.split_pdf_parts:
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover, dividir, extrair e gerir páginas de arquivos PDF. "
    "Inclui opção experimental de OCR (requer configuração do Tesseract no servidor). "
    "Desenvolvido com Streamlit e PyMuPDF."
)
if not OCR_AVAILABLE:
    st.sidebar.warning("A funcionalidade de OCR (tornar pesquisável) está limitada ou desabilitada pois `pymupdf-tesseract` não foi encontrado ou o Tesseract não está configurado no ambiente do servidor. Para ativá-la no Streamlit Cloud, adicione `tesseract-ocr` e `tesseract-ocr-por` ao seu `packages.txt` e `pymupdf-tesseract` ao `requirements.txt`.")

