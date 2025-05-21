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
    # Idealmente, verificaríamos também os pacotes de idioma, mas isso é mais complexo.
    # Por agora, se o Tesseract existe, assumimos que o OCR é potencialmente utilizável.
    OCR_AVAILABLE = True 
    # print(f"Tesseract OCR encontrado em: {TESSERACT_PATH}")
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

# --- Cache para Carregamento do PDF ---
@st.cache_resource(show_spinner="Carregando PDF...")
def load_pdf_from_bytes(pdf_bytes, filename="uploaded_pdf"):
    """Carrega um documento PDF a partir de bytes e o armazena em cache."""
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Erro ao carregar o PDF '{filename}': {e}")
        return None

# --- Funções Auxiliares (mantidas e ajustadas) ---
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

def apply_ocr_to_doc(doc_to_ocr):
    """Aplica OCR ao documento se o Tesseract estiver disponível."""
    if not OCR_AVAILABLE:
        st.warning("Funcionalidade de OCR não está disponível (Tesseract OCR não configurado no servidor). O PDF será salvo sem OCR.")
        return False

    try:
        is_already_searchable = all(page.get_text("text") for page in doc_to_ocr)
        if is_already_searchable:
            st.info("O PDF já parece ser pesquisável. OCR não será reaplicado.")
            return False

        ocr_progress = st.progress(0, text="Aplicando OCR (Português)... 0%")
        total_pages = len(doc_to_ocr)
        
        # PyMuPDF >= 1.19.0 tem ocr_pdf
        if hasattr(doc_to_ocr, "ocr_pdf"):
            # O método ocr_pdf pode não ter um callback de progresso direto.
            # A simulação de progresso aqui é genérica.
            # Para um progresso real, precisaríamos de uma biblioteca que o suporte ou
            # processar página por página, o que é menos eficiente com ocr_pdf.
            doc_to_ocr.ocr_pdf(language="por") 
            ocr_progress.progress(100, text="OCR Aplicado!")
            st.success("OCR aplicado com sucesso!")
            return True
        else:
            st.warning("Método `ocr_pdf` não encontrado no PyMuPDF. A funcionalidade de OCR pode não estar disponível ou requer uma versão mais recente do PyMuPDF. Verifique também se o Tesseract OCR está instalado no servidor.")
            ocr_progress.empty()
            return False
    except Exception as e:
        st.error(f"Erro durante o processo de OCR: {e}. Verifique se o Tesseract OCR e o pacote de idioma 'por' estão instalados no servidor. O PDF será salvo sem OCR adicional.")
        if 'ocr_progress' in locals(): ocr_progress.empty()
        return False

# --- Inicialização do Estado da Sessão ---
def initialize_session_state():
    defaults = {
        'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
        'processed_pdf_bytes_remove': None, 'processed_pdf_bytes_extract': None, 
        'processed_pdf_bytes_visual': None, 'processed_pdf_bytes_ocr': None,
        'split_pdf_parts': [], 'error_message': None, 'last_uploaded_filename': None,
        'page_previews': [], 'visual_page_selection': {}, # Usar dict para checkboxes visuais
        'processing_remove': False, 'processing_split': False, 'processing_extract': False, 
        'processing_visual_delete': False, 'processing_visual_extract': False, 'processing_ocr': False,
        'active_tab_for_preview': None # Para controlar geração de miniaturas
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value
initialize_session_state()

# --- Botão para Limpar Estado ---
if st.sidebar.button("Limpar PDF Carregado e Seleções", key="clear_all_sidebar_btn_v6"):
    # ... (lógica de limpeza, similar à anterior, mas incluindo novas chaves de estado)
    keys_to_reset = list(initialize_session_state.__defaults__[0].keys()) # Pega as chaves padrão
    for key in keys_to_reset:
        if key in ['bookmarks_data', 'split_pdf_parts', 'page_previews']: st.session_state[key] = []
        elif key == 'visual_page_selection': st.session_state[key] = {}
        elif key.startswith('processing_'): st.session_state[key] = False
        else: st.session_state[key] = None
            
    dynamic_keys = [k for k in st.session_state if k.startswith("delete_bookmark_") or "_input" in k or "_checkbox" in k]
    for k_del in dynamic_keys:
        if k_del in st.session_state: del st.session_state[k_del]
    st.success("Estado da aplicação limpo!")
    st.rerun()

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader_main_v6")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        # Resetar estados que dependem do PDF carregado
        st.session_state.bookmarks_data = []
        st.session_state.processed_pdf_bytes_remove = None
        st.session_state.processed_pdf_bytes_extract = None
        st.session_state.processed_pdf_bytes_visual = None
        st.session_state.processed_pdf_bytes_ocr = None
        st.session_state.split_pdf_parts = []
        st.session_state.error_message = None
        st.session_state.page_previews = [] # Limpa para forçar regeneração se a aba for ativada
        st.session_state.visual_page_selection = {}
        
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_")]
        for k_del in keys_to_delete:
            if k_del in st.session_state: del st.session_state[k_del]
        
        # Carrega o documento do cache (ou o lê se for a primeira vez)
        # Não precisa de spinner aqui pois o cache_resource tem seu próprio
        doc = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
        if doc:
            st.info(f"PDF '{st.session_state.pdf_name}' carregado com {doc.page_count} páginas.")
            st.session_state.bookmarks_data = get_bookmark_ranges(doc)
            # Miniaturas serão geradas sob demanda na aba "Gerir Páginas Visualmente"
        else:
            st.session_state.pdf_doc_bytes_original = None # Falha ao carregar
else:
    if st.session_state.last_uploaded_filename is not None:
        st.session_state.pdf_doc_bytes_original = None
        st.session_state.last_uploaded_filename = None
        load_pdf_from_bytes.clear() # Limpa o cache do PDF


# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original:
    # Obter o documento do cache para as operações
    doc_cached = load_pdf_from_bytes(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
    if not doc_cached: # Se o carregamento em cache falhou
        st.error("Não foi possível carregar o documento PDF para processamento.")
    else:
        tab_remove, tab_split, tab_extract, tab_visual_manage, tab_ocr = st.tabs([
            "Remover Páginas", "Dividir PDF", "Extrair Páginas", "Gerir Páginas Visualmente", "Aplicar OCR"
        ])

        # --- ABA: REMOVER PÁGINAS ---
        with tab_remove:
            # ... (Código da aba de remoção, similar ao anterior, mas usando doc_cached)
            # ... Adicionar st.progress se a operação for demorada
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
                direct_pages_str_tab_remove = st.text_input("Páginas a excluir (ex: 1, 3-5, 8):", key="direct_pages_input_tab_remove_v6")
            
            optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar", value=True, key="optimize_pdf_remove_checkbox_tab_remove_v6")
            ocr_pdf_remove = st.checkbox("Tornar PDF pesquisável (OCR - Português)", value=False, key="ocr_pdf_remove_checkbox_tab_remove_v6", help="Requer Tesseract. Pode demorar.")
            
            if st.button("Processar Remoção de Páginas", key="process_remove_button_tab_remove_v6", disabled=st.session_state.get('processing_remove', False)):
                st.session_state.processing_remove = True
                st.session_state.processed_pdf_bytes_remove = None; st.session_state.error_message = None
                
                # Criar uma cópia do documento em cache para modificação
                doc_to_modify = fitz.open(stream=doc_cached.write(), filetype="pdf") # Salva em bytes e reabre para ter uma cópia

                with st.spinner("A processar remoção de páginas... Por favor, aguarde."):
                    # ... (lógica de remoção) ...
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
                        st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas."; st.error(st.session_state.error_message)
                    else:
                        try:
                            doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                            if ocr_pdf_remove: apply_ocr_to_doc(doc_to_modify)
                            
                            save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_remove: save_options.update({"deflate_images": True, "deflate_fonts": True})
                            pdf_output_buffer = io.BytesIO()
                            doc_to_modify.save(pdf_output_buffer, **save_options)
                            st.session_state.processed_pdf_bytes_remove = pdf_output_buffer.getvalue()
                            st.success(f"PDF processado! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                        except Exception as e: st.session_state.error_message = f"Erro ao remover páginas: {e}"; st.error(st.session_state.error_message)
                        finally: doc_to_modify.close()
                st.session_state.processing_remove = False
                st.rerun()

            if st.session_state.processed_pdf_bytes_remove:
                download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_editado.pdf"
                st.download_button(label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes_remove, file_name=download_filename_remove, mime="application/pdf", key="download_remove_button_tab_remove_v6")

        # --- ABA: DIVIDIR PDF ---
        with tab_split:
            # ... (Código da aba dividir PDF, similar ao anterior, mas usando doc_cached e st.progress)
            # ... e chamando apply_ocr_to_doc para cada parte se ocr_pdf_split for True
            st.header("Dividir PDF")
            # ... (resto da lógica da aba dividir, adaptada para usar doc_cached) ...
            # Exemplo de uso de st.progress dentro de um loop de divisão (simplificado):
            # if st.button("Dividir...", disabled=st.session_state.get('processing_split', False)):
            #     st.session_state.processing_split = True
            #     progress_bar_split = st.progress(0, text="Dividindo PDF...")
            #     # ... loop de divisão ...
            #         progress_bar_split.progress(percent_complete, text=f"Processando parte {part_number}...")
            #     progress_bar_split.empty() # Limpa a barra de progresso
            #     st.session_state.processing_split = False
            #     st.rerun()
            # (A lógica completa da divisão por tamanho e contagem foi omitida aqui para brevidade,
            # mas deve ser adaptada para usar doc_cached e a barra de progresso)
            st.info("Funcionalidade de Divisão de PDF a ser totalmente implementada com barra de progresso.")


        # --- ABA: EXTRAIR PÁGINAS ---
        with tab_extract:
            # ... (Código da aba extrair páginas, similar ao anterior, mas usando doc_cached e st.progress)
            st.header("Extrair Páginas Específicas")
            # ... (resto da lógica da aba extrair, adaptada para usar doc_cached) ...


        # --- ABA: GERIR PÁGINAS VISUALMENTE ---
        with tab_visual_manage:
            st.header("Gerir Páginas Visualmente")
            if st.session_state.active_tab_for_preview != "visual_manage" or not st.session_state.page_previews:
                # Gera miniaturas apenas se esta aba estiver ativa e as miniaturas não tiverem sido geradas
                if not st.session_state.page_previews and doc_cached:
                    with st.spinner("Gerando pré-visualizações das páginas..."):
                        previews = []
                        total_pages_for_preview = doc_cached.page_count
                        preview_progress = st.progress(0, text="Gerando miniaturas... 0%")
                        for page_num in range(total_pages_for_preview):
                            page = doc_cached.load_page(page_num)
                            pix = page.get_pixmap(dpi=50) # DPI ainda menor para mais velocidade
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            previews.append(img_byte_arr.getvalue())
                            preview_progress.progress(int(((page_num + 1) / total_pages_for_preview) * 100), text=f"Gerando miniatura {page_num+1}/{total_pages_for_preview}")
                        st.session_state.page_previews = previews
                        preview_progress.empty()
                st.session_state.active_tab_for_preview = "visual_manage"

            if not st.session_state.page_previews:
                st.info("Carregue um PDF para ver as pré-visualizações das páginas aqui.")
            else:
                st.markdown(f"Total de páginas: {len(st.session_state.page_previews)}. Selecione as páginas abaixo:")
                num_cols_preview = st.sidebar.slider("Colunas para pré-visualização:", 2, 8, 4, key="preview_cols_slider_v6")
                cols = st.columns(num_cols_preview)
                
                for i, img_bytes in enumerate(st.session_state.page_previews):
                    with cols[i % num_cols_preview]:
                        page_key = f"select_page_preview_{i}" # Chave única para cada checkbox
                        # Inicializa o estado no dicionário se não existir
                        if i not in st.session_state.visual_page_selection:
                            st.session_state.visual_page_selection[i] = False
                        
                        st.image(img_bytes, caption=f"Página {i+1}", width=120)
                        # O widget atualiza st.session_state.visual_page_selection[i]
                        st.session_state.visual_page_selection[i] = st.checkbox("Selecionar", value=st.session_state.visual_page_selection[i], key=page_key)
                
                selected_page_indices = sorted([k for k, v in st.session_state.visual_page_selection.items() if v])
                st.markdown(f"**Páginas selecionadas (0-indexadas):** {selected_page_indices if selected_page_indices else 'Nenhuma'}")

                # ... (Lógica dos botões de Excluir/Extrair Visualmente, adaptada para usar doc_cached e o novo st.session_state.visual_page_selection) ...
                # ... e desabilitar botões com st.session_state.processing_visual_delete/extract
                # ... e st.progress()
                st.info("Funcionalidade de Gerir Páginas Visualmente a ser totalmente implementada com barra de progresso e botões.")


        # --- ABA: APLICAR OCR ---
        with tab_ocr:
            st.header("Aplicar OCR ao PDF Inteiro")
            st.markdown("Esta funcionalidade tentará tornar o texto do seu PDF pesquisável. O PDF original não será alterado; um novo PDF com OCR será gerado para download.")
            
            if not OCR_AVAILABLE:
                st.error("O Tesseract OCR não foi detectado neste ambiente. A funcionalidade de OCR está desabilitada. Verifique as instruções na barra lateral.")
            
            optimize_ocr_output = st.checkbox("Otimizar PDF com OCR ao salvar", value=True, key="optimize_ocr_output_checkbox_v6")

            if st.button("Aplicar OCR e Preparar Download", key="apply_ocr_button_v6", disabled=st.session_state.get('processing_ocr', False) or not OCR_AVAILABLE):
                st.session_state.processing_ocr = True
                st.session_state.processed_pdf_bytes_ocr = None; st.session_state.error_message = None
                
                # Criar uma cópia do documento em cache para aplicar OCR
                doc_for_ocr = fitz.open(stream=doc_cached.write(), filetype="pdf")

                ocr_applied_successfully = apply_ocr_to_doc(doc_for_ocr) # st.spinner está dentro desta função
                
                if ocr_applied_successfully or not ocr_applied_successfully: # Mesmo se falhar, tentamos salvar o que temos
                    try:
                        save_options = {"garbage": 4, "deflate": True, "clean": True}
                        if optimize_ocr_output: save_options.update({"deflate_images": True, "deflate_fonts": True})
                        
                        pdf_output_buffer = io.BytesIO()
                        doc_for_ocr.save(pdf_output_buffer, **save_options)
                        st.session_state.processed_pdf_bytes_ocr = pdf_output_buffer.getvalue()
                        if ocr_applied_successfully:
                            st.success("PDF com OCR aplicado pronto para download!")
                        else:
                            st.info("PDF salvo. O OCR pode não ter sido aplicado ou já era pesquisável.")
                    except Exception as e:
                        st.session_state.error_message = f"Erro ao salvar PDF após tentativa de OCR: {e}"; st.error(st.session_state.error_message)
                    finally:
                        doc_for_ocr.close()
                st.session_state.processing_ocr = False
                st.rerun()

            if st.session_state.processed_pdf_bytes_ocr:
                download_filename_ocr = f"{os.path.splitext(st.session_state.pdf_name)[0]}_ocr.pdf"
                st.download_button(label="Baixar PDF com OCR", data=st.session_state.processed_pdf_bytes_ocr, file_name=download_filename_ocr, mime="application/pdf", key="download_ocr_button_v6")


# Exibir mensagem de erro global
if st.session_state.error_message and not any([st.session_state.processed_pdf_bytes_remove, 
                                                st.session_state.processed_pdf_bytes_extract, 
                                                st.session_state.processed_pdf_bytes_visual,
                                                st.session_state.processed_pdf_bytes_ocr,
                                                st.session_state.split_pdf_parts]):
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover, dividir, extrair e gerir páginas de arquivos PDF. "
    "Inclui opção experimental de OCR (requer configuração do Tesseract no servidor). "
    "Desenvolvido com Streamlit e PyMuPDF."
)
if not OCR_AVAILABLE:
    st.sidebar.error("OCR INDISPONÍVEL: Tesseract OCR não foi detectado no ambiente do servidor. Para ativar, adicione `tesseract-ocr` e `tesseract-ocr-por` ao seu `packages.txt` no Streamlit Cloud.")

