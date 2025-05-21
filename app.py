import streamlit as st
import fitz  # PyMuPDF
import os
import io # Para trabalhar com bytes em memória
import zipfile # Para criar arquivos ZIP

# Configuração da página
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF")

st.title("✂️ Editor e Divisor de PDF Avançado")
st.markdown("""
    **Funcionalidades:**
    1.  **Remover Páginas:** Carregue um PDF, selecione marcadores (bookmarks) para remover as seções correspondentes ou insira números de página/intervalos diretamente.
    2.  **Dividir PDF:** Divida um PDF grande em partes menores com base em um tamanho máximo especificado.
""")

# --- Funções Auxiliares ---

def get_bookmark_ranges(pdf_doc):
    bookmarks_data = []
    if not pdf_doc:
        return bookmarks_data
    try:
        toc = pdf_doc.get_toc(simple=False)
    except Exception as e:
        st.error(f"Erro ao obter marcadores: {e}")
        return bookmarks_data
    if not toc:
        return bookmarks_data

    num_total_pages_doc = pdf_doc.page_count
    for i, item_i in enumerate(toc):
        if len(item_i) < 3:
            print(f"Aviso: Item de marcador com formato inesperado: {item_i}. Pulando.")
            continue
        level_i, title_i, page_num_1_indexed_i = item_i[0], item_i[1], item_i[2]
        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc):
            print(f"Aviso: Marcador '{title_i}' aponta para página inicial inválida ({page_num_1_indexed_i}). Pulando.")
            continue
        
        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = num_total_pages_doc - 1
        
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            level_j, _, page_num_1_indexed_j = item_j[0], item_j[1], item_j[2]
            if not (1 <= page_num_1_indexed_j <= num_total_pages_doc): continue
            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j - 2 
                break 
        
        end_page_0_idx = max(start_page_0_idx, end_page_0_idx)
        end_page_0_idx = min(end_page_0_idx, num_total_pages_doc - 1)
        display_text = f"{'➡️' * level_i} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        bookmarks_data.append({
            "title": title_i, "start_page_0_idx": start_page_0_idx,
            "end_page_0_idx": end_page_0_idx, "level": level_i,
            "display_text": display_text, "id": f"bookmark_{i}" # Usar um ID estável para o marcador
        })
    return bookmarks_data

def parse_direct_page_input(page_str, max_page_1_idx):
    pages_to_delete_0_indexed = set()
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
                    if 1 <= i <= max_page_1_idx: pages_to_delete_0_indexed.add(i - 1) 
                    else: st.warning(f"Aviso: Página {i} (entrada direta) fora do intervalo (1-{max_page_1_idx}).")
            elif part: 
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx: pages_to_delete_0_indexed.add(page_num_1_idx - 1) 
                else: st.warning(f"Aviso: Página {page_num_1_idx} (entrada direta) fora do intervalo (1-{max_page_1_idx}).")
        except ValueError: st.warning(f"Aviso: Entrada de página inválida '{part}'.")
    return sorted(list(pages_to_delete_0_indexed))

# --- Inicialização do Estado da Sessão ---
if 'pdf_doc_bytes_original' not in st.session_state:
    st.session_state.pdf_doc_bytes_original = None
if 'pdf_name' not in st.session_state:
    st.session_state.pdf_name = None
if 'bookmarks_data' not in st.session_state:
    st.session_state.bookmarks_data = []
if 'processed_pdf_bytes' not in st.session_state:
    st.session_state.processed_pdf_bytes = None
if 'split_pdf_parts' not in st.session_state:
    st.session_state.split_pdf_parts = []
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'last_uploaded_filename' not in st.session_state:
    st.session_state.last_uploaded_filename = None

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf", key="pdf_uploader")

if uploaded_file is not None:
    if st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
        st.session_state.pdf_name = uploaded_file.name
        st.session_state.last_uploaded_filename = uploaded_file.name
        
        # Resetar estados específicos ao carregar um NOVO arquivo
        st.session_state.bookmarks_data = []
        st.session_state.processed_pdf_bytes = None
        st.session_state.split_pdf_parts = []
        st.session_state.error_message = None
        
        # Limpar chaves de checkboxes de marcadores do PDF anterior
        keys_to_delete = [k for k in st.session_state if k.startswith("delete_bookmark_")]
        for k_del in keys_to_delete:
            del st.session_state[k_del]
        
        try:
            # Usar 'with' para garantir que o documento seja fechado
            with fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf") as temp_doc:
                st.info(f"PDF '{st.session_state.pdf_name}' carregado com {temp_doc.page_count} páginas.")
                st.session_state.bookmarks_data = get_bookmark_ranges(temp_doc)
        except Exception as e:
            st.session_state.error_message = f"Erro ao abrir ou processar o PDF: {e}"
            st.error(st.session_state.error_message)
            st.session_state.pdf_doc_bytes_original = None 
else:
    # Se nenhum arquivo estiver carregado (ou for removido), resetar o nome do último arquivo para forçar o reload
    if st.session_state.last_uploaded_filename is not None:
        st.session_state.last_uploaded_filename = None # Força o reset na próxima vez que um arquivo for carregado
        # Considerar resetar outros estados aqui também se necessário,
        # mas o bloco acima já cobre o reset quando um *novo* arquivo é carregado.
        # Se o arquivo é simplesmente "des-carregado", os estados podem persistir até o próximo upload.

# --- Abas para diferentes funcionalidades ---
if st.session_state.pdf_doc_bytes_original: # Verifica se há bytes de um PDF carregado
    tab1, tab2 = st.tabs(["Remover Páginas", "Dividir PDF por Tamanho"])

    with tab1:
        st.header("Remover Páginas do PDF")
        if st.session_state.bookmarks_data:
            st.subheader("Marcadores para Excluir:")
            st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
            with st.container(height=300):
                for bm in st.session_state.bookmarks_data:
                    checkbox_key = f"delete_bookmark_{bm['id']}"
                    # Inicializa o estado no session_state se não existir
                    if checkbox_key not in st.session_state:
                        st.session_state[checkbox_key] = False
                    
                    # O widget st.checkbox LÊ de st.session_state[checkbox_key]
                    # e ATUALIZA st.session_state[checkbox_key] na interação.
                    st.checkbox(
                        label=bm['display_text'], 
                        value=st.session_state[checkbox_key], 
                        key=checkbox_key 
                    )
        else:
            st.info("Nenhum marcador encontrado para remoção.")

        st.subheader("Páginas para Excluir Diretamente:")
        direct_pages_str_tab1 = st.text_input("Números das páginas (ex: 1, 3-5, 8):", key="direct_pages_input_tab1")
        optimize_pdf_remove = st.checkbox("Otimizar PDF ao salvar (pode afetar qualidade)", value=True, key="optimize_pdf_remove_checkbox")

        if st.button("Processar e Preparar para Download (Remoção)", key="process_remove_button"):
            st.session_state.processed_pdf_bytes = None # Limpar download anterior
            st.session_state.error_message = None
            
            # Abrir o documento a partir dos bytes originais para esta operação
            doc_to_modify = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")

            selected_bookmark_pages_to_delete = set()
            if st.session_state.bookmarks_data:
                for bm in st.session_state.bookmarks_data:
                    checkbox_key = f"delete_bookmark_{bm['id']}"
                    if st.session_state.get(checkbox_key, False): # Lê o valor do session_state
                        for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                            selected_bookmark_pages_to_delete.add(page_num)
            
            direct_pages_to_delete_list = parse_direct_page_input(direct_pages_str_tab1, doc_to_modify.page_count)
            all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

            if not all_pages_to_delete_0_indexed:
                st.warning("Nenhum marcador ou página foi selecionado para exclusão.")
            elif len(all_pages_to_delete_0_indexed) >= doc_to_modify.page_count:
                st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas do PDF."
                st.error(st.session_state.error_message)
            else:
                try:
                    doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                    save_options = {"garbage": 4, "deflate": True, "clean": True}
                    if optimize_pdf_remove:
                        save_options["deflate_images"] = True
                        save_options["deflate_fonts"] = True
                    
                    pdf_output_buffer = io.BytesIO()
                    doc_to_modify.save(pdf_output_buffer, **save_options)
                    pdf_output_buffer.seek(0)
                    st.session_state.processed_pdf_bytes = pdf_output_buffer.getvalue()
                    st.success(f"PDF processado para remoção! {len(all_pages_to_delete_0_indexed)} página(s) removida(s).")
                except Exception as e:
                    st.session_state.error_message = f"Erro ao processar o PDF para remoção: {e}"
                    st.error(st.session_state.error_message)
                finally:
                    doc_to_modify.close() # Fechar o documento após o uso

        if st.session_state.processed_pdf_bytes:
            download_filename_remove = f"{os.path.splitext(st.session_state.pdf_name)[0]}_editado.pdf"
            st.download_button(
                label="Baixar PDF Editado", data=st.session_state.processed_pdf_bytes,
                file_name=download_filename_remove, mime="application/pdf", key="download_remove_button"
            )

    with tab2:
        st.header("Dividir PDF por Tamanho")
        max_size_mb = st.number_input("Tamanho máximo por parte (MB):", min_value=0.1, value=5.0, step=0.1, format="%.1f", key="max_size_mb_input")
        optimize_pdf_split = st.checkbox("Otimizar partes divididas (pode afetar qualidade)", value=True, key="optimize_pdf_split_checkbox")

        if st.button("Dividir PDF por Tamanho", key="split_button"):
            st.session_state.split_pdf_parts = [] 
            st.session_state.error_message = None
            
            if not st.session_state.pdf_doc_bytes_original:
                st.error("Por favor, carregue um arquivo PDF primeiro.")
            else:
                max_size_bytes = int(max_size_mb * 1024 * 1024)
                
                try:
                    # Abrir o documento original a partir dos bytes armazenados
                    original_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                    total_pages_original = original_doc.page_count
                    current_page_index = 0
                    part_number = 1

                    while current_page_index < total_pages_original:
                        new_part_doc = fitz.open() 
                        current_part_size = 0
                        pages_in_current_part = 0

                        while current_page_index < total_pages_original:
                            temp_doc_for_size_check = fitz.open()
                            if pages_in_current_part > 0: # Se já tem páginas na parte atual
                                temp_doc_for_size_check.insert_pdf(new_part_doc)
                            temp_doc_for_size_check.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                            
                            temp_buffer = io.BytesIO()
                            save_options_check = {"garbage": 0, "deflate": optimize_pdf_split}
                            if optimize_pdf_split:
                                save_options_check["deflate_images"] = True
                                save_options_check["deflate_fonts"] = True
                            temp_doc_for_size_check.save(temp_buffer, **save_options_check)
                            estimated_size = len(temp_buffer.getvalue())
                            temp_doc_for_size_check.close()
                            temp_buffer.close()

                            if pages_in_current_part > 0 and estimated_size > max_size_bytes:
                                break 
                            
                            new_part_doc.insert_pdf(original_doc, from_page=current_page_index, to_page=current_page_index)
                            current_part_size = estimated_size
                            current_page_index += 1
                            pages_in_current_part += 1

                            if current_part_size > max_size_bytes and pages_in_current_part == 1:
                                st.warning(f"Página {current_page_index} (sozinha) excede o limite de {max_size_mb}MB. Será uma parte separada.")
                                break
                        
                        if pages_in_current_part > 0:
                            part_buffer = io.BytesIO()
                            final_save_options = {"garbage": 4, "deflate": True, "clean": True}
                            if optimize_pdf_split:
                                final_save_options["deflate_images"] = True
                                final_save_options["deflate_fonts"] = True
                            new_part_doc.save(part_buffer, **final_save_options)
                            part_buffer.seek(0)
                            
                            part_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_parte_{part_number}.pdf"
                            st.session_state.split_pdf_parts.append({"name": part_filename, "data": part_buffer.getvalue()})
                            part_number += 1
                        new_part_doc.close()
                    
                    original_doc.close() # Fechar o documento original após o uso
                    if st.session_state.split_pdf_parts:
                        st.success(f"PDF dividido em {len(st.session_state.split_pdf_parts)} partes!")
                    else:
                        st.warning("Não foi possível dividir o PDF com os critérios fornecidos, ou o PDF original está vazio.")

                except Exception as e:
                    st.session_state.error_message = f"Erro ao dividir o PDF: {e}"
                    st.error(st.session_state.error_message)
        
        if st.session_state.split_pdf_parts:
            st.subheader("Baixar Partes do PDF:")
            
            if len(st.session_state.split_pdf_parts) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for part in st.session_state.split_pdf_parts:
                        zip_file.writestr(part["name"], part["data"])
                zip_buffer.seek(0)
                
                st.download_button(
                    label=f"Baixar Todas as Partes ({len(st.session_state.split_pdf_parts)}) como ZIP",
                    data=zip_buffer,
                    file_name=f"{os.path.splitext(st.session_state.pdf_name)[0]}_partes.zip",
                    mime="application/zip",
                    key="download_zip_button"
                )
                st.markdown("---")

            for i, part in enumerate(st.session_state.split_pdf_parts):
                st.download_button(
                    label=f"Baixar {part['name']}",
                    data=part["data"],
                    file_name=part["name"],
                    mime="application/pdf",
                    key=f"download_part_{i}_button"
                )

# Exibir mensagem de erro persistente, se houver (fora das abas)
if st.session_state.error_message and not st.session_state.processed_pdf_bytes and not st.session_state.split_pdf_parts:
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover páginas de um PDF e dividi-lo em partes menores. "
    "Desenvolvido com Streamlit e PyMuPDF."
)
