import streamlit as st
import fitz  # PyMuPDF
import os
import io # Para trabalhar com bytes em memória

# Configuração da página
st.set_page_config(layout="wide", page_title="Editor de PDF Simples")

st.title("✂️ Editor de PDF Simples")
st.markdown("""
    Carregue um arquivo PDF para listar seus marcadores (bookmarks) e/ou especificar páginas para exclusão.
    Você pode selecionar marcadores para remover as seções correspondentes ou inserir números de páginas/intervalos diretamente.
""")

# --- Funções Auxiliares (adaptadas da lógica Tkinter) ---

def get_bookmark_ranges(pdf_doc):
    """
    Extrai os marcadores e os intervalos de página (0-indexado) que eles cobrem.
    Retorna uma lista de dicionários, cada um com 'title', 'start_page_0_idx', 'end_page_0_idx', 'level', 'display_text'.
    """
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

        level_i = item_i[0]
        title_i = item_i[1]
        page_num_1_indexed_i = item_i[2]

        if not (1 <= page_num_1_indexed_i <= num_total_pages_doc):
            print(f"Aviso: Marcador '{title_i}' aponta para página inicial inválida ({page_num_1_indexed_i}). Pulando.")
            continue
        
        start_page_0_idx = page_num_1_indexed_i - 1
        end_page_0_idx = num_total_pages_doc - 1 # Padrão: vai até o fim
        
        for j in range(i + 1, len(toc)):
            item_j = toc[j]
            if len(item_j) < 3: continue
            
            level_j = item_j[0]
            page_num_1_indexed_j = item_j[2]

            if not (1 <= page_num_1_indexed_j <= num_total_pages_doc):
                continue

            if level_j <= level_i:
                end_page_0_idx = page_num_1_indexed_j - 2 
                break 
        
        end_page_0_idx = max(start_page_0_idx, end_page_0_idx)
        end_page_0_idx = min(end_page_0_idx, num_total_pages_doc - 1)

        display_text = f"{'➡️' * level_i} {title_i} (Páginas {start_page_0_idx + 1} a {end_page_0_idx + 1})"
        
        bookmarks_data.append({
            "title": title_i,
            "start_page_0_idx": start_page_0_idx,
            "end_page_0_idx": end_page_0_idx,
            "level": level_i,
            "display_text": display_text,
            "id": f"bookmark_{i}" # ID único para o widget Streamlit
        })
    return bookmarks_data

def parse_direct_page_input(page_str, max_page_1_idx):
    pages_to_delete_0_indexed = set()
    if not page_str.strip():
        return []
    
    parts = page_str.split(',')
    for part in parts:
        part = part.strip()
        try:
            if '-' in part:
                start_str, end_str = part.split('-')
                start_1_idx = int(start_str.strip())
                end_1_idx = int(end_str.strip())
                if start_1_idx > end_1_idx: 
                    start_1_idx, end_1_idx = end_1_idx, start_1_idx
                for i in range(start_1_idx, end_1_idx + 1):
                    if 1 <= i <= max_page_1_idx:
                        pages_to_delete_0_indexed.add(i - 1) 
                    else:
                        st.warning(f"Aviso: Página {i} na entrada direta está fora do intervalo (1-{max_page_1_idx}). Ignorando.")
            elif part: 
                page_num_1_idx = int(part)
                if 1 <= page_num_1_idx <= max_page_1_idx:
                    pages_to_delete_0_indexed.add(page_num_1_idx - 1) 
                else:
                    st.warning(f"Aviso: Página {page_num_1_idx} na entrada direta está fora do intervalo (1-{max_page_1_idx}). Ignorando.")
        except ValueError:
            st.warning(f"Aviso: Entrada de página inválida '{part}'. Ignorando.")
    return sorted(list(pages_to_delete_0_indexed))

# --- Inicialização do Estado da Sessão ---
if 'pdf_doc' not in st.session_state:
    st.session_state.pdf_doc = None
if 'pdf_name' not in st.session_state:
    st.session_state.pdf_name = None
if 'bookmarks_data' not in st.session_state:
    st.session_state.bookmarks_data = []
if 'processed_pdf_bytes' not in st.session_state:
    st.session_state.processed_pdf_bytes = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Carregue seu arquivo PDF", type="pdf")

if uploaded_file is not None:
    # Se um novo arquivo for carregado, resetar o estado anterior
    if st.session_state.pdf_name != uploaded_file.name:
        st.session_state.pdf_doc = None
        st.session_state.bookmarks_data = []
        st.session_state.processed_pdf_bytes = None
        st.session_state.error_message = None
        # Limpar seleções de marcadores anteriores
        for key in list(st.session_state.keys()):
            if key.startswith("delete_bookmark_"):
                del st.session_state[key]

    st.session_state.pdf_name = uploaded_file.name
    try:
        # Ler os bytes do arquivo carregado
        pdf_bytes = uploaded_file.getvalue()
        st.session_state.pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        st.info(f"PDF '{st.session_state.pdf_name}' carregado com {st.session_state.pdf_doc.page_count} páginas.")
        
        # Carregar marcadores
        st.session_state.bookmarks_data = get_bookmark_ranges(st.session_state.pdf_doc)

    except Exception as e:
        st.session_state.error_message = f"Erro ao abrir ou processar o PDF: {e}"
        st.session_state.pdf_doc = None # Garante que não tentaremos processar um doc inválido
        st.error(st.session_state.error_message)

# --- Exibição e Seleção de Marcadores (se o PDF estiver carregado) ---
if st.session_state.pdf_doc:
    if st.session_state.bookmarks_data:
        st.subheader("Marcadores para Excluir:")
        st.markdown("Selecione os marcadores cujos intervalos de páginas você deseja excluir.")
        
        # Usar um container com altura fixa e scroll para a lista de marcadores
        with st.container(height=300): # Ajuste a altura conforme necessário
            for bm in st.session_state.bookmarks_data:
                # Inicializar o estado do checkbox se não existir
                if f"delete_bookmark_{bm['id']}" not in st.session_state:
                    st.session_state[f"delete_bookmark_{bm['id']}"] = False
                
                # Usar st.checkbox e atualizar o session_state diretamente
                st.session_state[f"delete_bookmark_{bm['id']}"] = st.checkbox(
                    bm['display_text'], 
                    value=st.session_state[f"delete_bookmark_{bm['id']}"], # Ler valor do session_state
                    key=f"delete_bookmark_{bm['id']}" # Chave única
                )
    else:
        st.info("Nenhum marcador encontrado neste PDF.")

    st.subheader("Páginas para Excluir Diretamente:")
    direct_pages_str = st.text_input("Números das páginas (ex: 1, 3-5, 8):", key="direct_pages_input")

    st.subheader("Opções de Salvamento:")
    optimize_pdf = st.checkbox("Otimizar PDF (pode afetar qualidade de imagens/fontes)", value=True, key="optimize_pdf_checkbox")

    if st.button("Processar e Preparar para Download", key="process_button"):
        st.session_state.processed_pdf_bytes = None # Limpar download anterior
        st.session_state.error_message = None

        selected_bookmark_pages_to_delete = set()
        if st.session_state.bookmarks_data:
            for bm in st.session_state.bookmarks_data:
                if st.session_state.get(f"delete_bookmark_{bm['id']}", False):
                    for page_num in range(bm["start_page_0_idx"], bm["end_page_0_idx"] + 1):
                        selected_bookmark_pages_to_delete.add(page_num)
        
        direct_pages_to_delete_list = parse_direct_page_input(direct_pages_str, st.session_state.pdf_doc.page_count)
        
        all_pages_to_delete_0_indexed = sorted(list(selected_bookmark_pages_to_delete.union(set(direct_pages_to_delete_list))))

        if not all_pages_to_delete_0_indexed:
            st.warning("Nenhum marcador ou página foi selecionado para exclusão.")
        elif len(all_pages_to_delete_0_indexed) >= st.session_state.pdf_doc.page_count:
            st.session_state.error_message = "Erro: Não é permitido excluir todas as páginas do PDF."
            st.error(st.session_state.error_message)
        else:
            try:
                # Reabrir o PDF a partir dos bytes originais para cada processamento
                # para evitar modificar o st.session_state.pdf_doc em memória de forma acumulativa
                pdf_bytes_original = uploaded_file.getvalue() # Pega os bytes originais novamente
                doc_to_modify = fitz.open(stream=pdf_bytes_original, filetype="pdf")
                
                doc_to_modify.delete_pages(all_pages_to_delete_0_indexed)
                
                save_options = {
                    "garbage": 4,
                    "deflate": True,
                    "clean": True
                }
                if optimize_pdf: # Usa o valor atual do checkbox
                    save_options["deflate_images"] = True
                    save_options["deflate_fonts"] = True
                
                # Salvar em um buffer de bytes
                pdf_output_buffer = io.BytesIO()
                doc_to_modify.save(pdf_output_buffer, **save_options)
                pdf_output_buffer.seek(0) # Resetar o ponteiro do buffer para o início
                st.session_state.processed_pdf_bytes = pdf_output_buffer.getvalue()
                
                doc_to_modify.close()
                st.success(f"PDF processado! {len(all_pages_to_delete_0_indexed)} página(s) marcada(s) para exclusão. Clique no botão abaixo para baixar.")

            except Exception as e:
                st.session_state.error_message = f"Erro ao processar o PDF: {e}"
                st.error(st.session_state.error_message)

# --- Botão de Download (se um PDF foi processado) ---
if st.session_state.processed_pdf_bytes:
    download_filename = f"{os.path.splitext(st.session_state.pdf_name)[0]}_modificado.pdf"
    st.download_button(
        label="Baixar PDF Modificado",
        data=st.session_state.processed_pdf_bytes,
        file_name=download_filename,
        mime="application/pdf",
        key="download_button"
    )
    st.caption(f"Ao clicar, você baixará '{download_filename}'.")

# Exibir mensagem de erro persistente, se houver
if st.session_state.error_message and not st.session_state.processed_pdf_bytes: # Só mostra se não houver download pronto
    st.error(st.session_state.error_message)

st.sidebar.header("Sobre")
st.sidebar.info(
    "Este aplicativo permite remover páginas de um PDF com base na seleção de marcadores "
    "ou inserindo números de página diretamente. Desenvolvido com Streamlit e PyMuPDF."
)
