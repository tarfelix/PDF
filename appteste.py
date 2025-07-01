# ===========================================================
# IMPORTS E CONFIGURAÇÃO INICIAL
# ===========================================================
import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
import os
import copy
from unidecode import unidecode

# Configura a página do Streamlit para usar o layout "wide" e define um título
st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")

# Constante para o limite de tamanho do arquivo que habilita a aba de preview visual.
# Arquivos maiores que isso podem causar lentidão ou travamentos no navegador.
VISUAL_PREVIEW_SIZE_LIMIT_MB = 50

# ===========================================================
# FUNÇÕES AUXILIARES E DE COMPATIBILIDADE
# ===========================================================

def insert_pages(dst: fitz.Document, src: fitz.Document, pages: list[int]):
    """
    Insere uma lista de páginas de um documento de origem (src) para um de destino (dst).
    Esta função é projetada para ser compatível com múltiplas versões da biblioteca PyMuPDF,
    tentando diferentes métodos de inserção e, como último recurso, inserindo uma página de cada vez,
    que é a forma mais robusta de lidar com listas de páginas não contíguas.
    """
    try:
        # Tentativa para versões mais antigas que suportavam o argumento 'subpages'
        dst.insert_pdf(src, subpages=pages)
    except TypeError:
        try:
            # Tentativa para outras versões que poderiam usar o argumento 'pages'
            dst.insert_pdf(src, pages=pages)
        except TypeError:
            # Método de fallback mais compatível: inserir uma página de cada vez.
            # Esta é a maneira correta para listas de páginas não contíguas em versões recentes.
            for p in pages:
                dst.insert_pdf(src, from_page=p, to_page=p)

def generate_download_button(doc_to_save, filename, button_text, optimize_options=None, password=""):
    """
    Salva um documento PyMuPDF em memória, aplica opções de otimização e senha,
    e gera um botão de download no Streamlit para o arquivo resultante.
    """
    if optimize_options is None:
        optimize_options = {}
    
    # Opções padrão de salvamento para limpar e comprimir o PDF
    save_opts = dict(garbage=4, deflate=True, clean=True, **optimize_options)
    
    # Se uma senha for fornecida, adiciona as opções de criptografia
    if password:
        save_opts.update({
            "encryption": fitz.ENCRYPT_AES_256,  # Criptografia forte
            "user_pw": password,
            "owner_pw": password,
            "permissions": fitz.PERM_PRINT | fitz.PERM_COPY | fitz.PERM_ANNOTATE
        })
        
    try:
        # Salva o documento em um buffer de bytes na memória
        buf = doc_to_save.tobytes(**save_opts)
        doc_to_save.close() # Fecha o documento para liberar memória
        
        # Cria o botão de download no Streamlit
        st.download_button(label=f"⬇️ {button_text}", data=buf, file_name=filename, mime="application/pdf")
        st.success(f"Seu arquivo '{filename}' está pronto para download!")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo para download: {e}")

# ===========================================================
# GERENCIAMENTO DO ESTADO DA SESSÃO (SESSION STATE)
# ===========================================================

# Define o estado padrão inicial da aplicação
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'last_uploaded_file_ids': [], 'page_previews': [], 'visual_page_selection': {},
    'files_to_merge': [], 'found_legal_pieces': [],
    'is_single_pdf_mode': False, # Controla se a UI é para um ou múltiplos arquivos
    'visual_tab_enabled': False, # Controla se a aba 'Visual' é exibida
}

def initialize_session_state():
    """
    Reseta o estado da aplicação para o padrão.
    Isso é crucial para garantir que, ao carregar novos arquivos,
    não haja dados residuais de sessões anteriores.
    """
    # Limpa chaves de widgets geradas dinamicamente para evitar erros do Streamlit
    dyn_keys = [
        k for k in st.session_state.keys() 
        if k.startswith((
            "delete_bookmark_", "extract_bookmark_", "select_page_preview_", 
            "legal_piece_", "up_", "down_"
            )) or k.endswith(("_input", "_checkbox"))
    ]
    for k in dyn_keys:
        st.session_state.pop(k, None)
    
    # Recria o estado padrão a partir do dicionário DEFAULT_STATE
    for k, v in DEFAULT_STATE.items():
        st.session_state[k] = copy.deepcopy(v)

# Inicializa o estado apenas uma vez quando o app é carregado pela primeira vez
if 'initialized_once' not in st.session_state:
    initialize_session_state()
    st.session_state.initialized_once = True

# ===========================================================
# PALAVRAS-CHAVE E FUNÇÕES CACHEADAS
# ===========================================================

LEGAL_KEYWORDS = {
    "Petição Inicial": ['petição inicial', 'inicial'],
    "Defesa/Contestação": ['defesa', 'contestação', 'contestacao'],
    "Réplica": ['réplica', 'replica', 'impugnação à contestação', 'impugnacao a contestacao'],
    "Sentença": ['sentença', 'sentenca'],
    "Acórdão": ['acórdão', 'acordao'],
    "Decisão": ['decisão', 'decisao', 'decisão interlocutória', 'decisao interlocutoria'],
    "Despacho": ['despacho'],
    "Recurso": ['recurso', 'agravo', 'embargos', 'apelação', 'apelacao'],
    "Ata de Audiência": ['ata de audiência', 'ata de audiencia', 'termo de audiência', 'termo de audiencia'],
    "Laudo": ['laudo', 'parecer técnico', 'parecer tecnico'],
    "Manifestação": ['manifestação', 'manifestacao', 'petição', 'peticao'],
    "Documento": ['documento'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'indice', 'sumário', 'sumario'],
}
PRE_SELECTED_LEGAL_CATEGORIES = [
    "Petição Inicial", "Sentença", "Acórdão", "Decisão", "Despacho", 
    "Defesa/Contestação", "Réplica", "Recurso", "Ata de Audiência", "Laudo", "Manifestação"
]

@st.cache_resource(show_spinner="Gerando miniaturas do PDF...")
def build_previews(pdf_bytes: bytes, dpi=48):
    """Gera imagens PNG de cada página do PDF para a aba 'Visual'."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [pg.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72)).tobytes("png") for pg in doc]

@st.cache_data(max_entries=5, show_spinner="Analisando metadados do PDF...")
def get_pdf_metadata(pdf_bytes: bytes, name="pdf"):
    """Extrai os marcadores (bookmarks) e a contagem de páginas de um PDF."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            return get_bookmark_ranges(d), d.page_count, None
    except Exception as e:
        return [], 0, f"Erro ao ler o arquivo {name}: {e}"

@st.cache_resource(show_spinner="Carregando documento PDF...")
def get_pdf_document(_pdf_bytes):
    """Abre um documento PDF a partir de bytes e o mantém em cache."""
    if not _pdf_bytes: return None
    try:
        return fitz.open(stream=_pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Não foi possível abrir o PDF: {e}")
        return None

def get_bookmark_ranges(doc: fitz.Document):
    """
    Processa o sumário (TOC) do PDF para determinar o intervalo de páginas de cada marcador.
    A lógica deduz a página final de um marcador observando a página inicial do próximo marcador
    de nível hierárquico igual ou superior.
    """
    toc = doc.get_toc(simple=False)
    res = []
    for i, (lvl, title, page1, *_) in enumerate(toc):
        if not 1 <= page1 <= doc.page_count: continue
        start0, end0 = page1 - 1, doc.page_count - 1
        for j in range(i + 1, len(toc)):
            if toc[j][0] <= lvl:
                end0 = toc[j][2] - 2
                break
        end0 = max(start0, min(end0, doc.page_count - 1))
        disp = f"{'➡️' * (lvl - 1)}{'↪️' if lvl > 1 else ''} {title} (Págs. {start0 + 1}-{end0 + 1})"
        res.append({"id": f"bm_{i}_{page1}", "display_text": disp, "start_page_0_idx": start0, "end_page_0_idx": end0, "title": title})
    return res

def find_legal_sections(bms):
    """Identifica peças jurídicas com base em palavras-chave nos títulos dos marcadores."""
    out = []
    for i, bm in enumerate(bms):
        norm = unidecode(bm['title']).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({**bm, 'category': cat, 'unique_id': f"legal_{i}_{bm['id']}", 'preselect': cat in PRE_SELECTED_LEGAL_CATEGORIES})
                break
    return out

def parse_page_input(inp: str, max1: int):
    """Converte uma string de entrada (ex: '1, 3-5, 10') em uma lista de índices de página."""
    sel = set()
    if not inp: return []
    for part in inp.split(','):
        part = part.strip()
        if not part: continue
        try:
            if '-' in part:
                a, b = map(int, part.split('-'))
                if a > b: a, b = b, a
                sel.update(i - 1 for i in range(a, b + 1) if 1 <= i <= max1)
            else:
                p = int(part)
                if 1 <= p <= max1: sel.add(p - 1)
        except ValueError:
            st.warning(f"Entrada inválida ignorada: '{part}'")
    return sorted(list(sel))

# ===========================================================
# INTERFACE PRINCIPAL DO STREAMLIT
# ===========================================================
st.title("✂️ Editor e Divisor de PDF Completo (PT-BR)")
st.markdown("Carregue um ou mais PDFs. **Arquivos muito grandes (> 50 MB) terão a aba 'Visual' desabilitada para evitar travamentos.**")

st.sidebar.button("🔄 Limpar Tudo e Recomeçar", on_click=initialize_session_state, type="primary")

uploaded_files = st.file_uploader("📄 Carregue seu(s) PDF(s) aqui", type="pdf", accept_multiple_files=True)

# ---------------- LÓGICA DE UPLOAD E ATUALIZAÇÃO DE ESTADO -----------------
if uploaded_files:
    file_ids = sorted(f.file_id for f in uploaded_files)
    # Se a lista de arquivos mudou, reseta todo o estado para começar do zero
    if file_ids != st.session_state.last_uploaded_file_ids:
        initialize_session_state()
        st.session_state.last_uploaded_file_ids = file_ids

        # Modo de edição de arquivo único
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            uploaded_file = uploaded_files[0]
            
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.session_state.visual_tab_enabled = file_size_mb <= VISUAL_PREVIEW_SIZE_LIMIT_MB

            if not st.session_state.visual_tab_enabled:
                st.warning(f"⚠️ Arquivo grande ({file_size_mb:.1f} MB). A aba 'Visual' foi desabilitada.")

            st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
            st.session_state.pdf_name = uploaded_file.name
            
            bms, pages, err = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, st.session_state.pdf_name)
            if err:
                st.error(err)
                st.session_state.is_single_pdf_mode = False # Falha ao ler, desativa modo single
            else:
                st.session_state.bookmarks_data = bms
                st.session_state.found_legal_pieces = find_legal_sections(bms)
                st.info(f"PDF '{st.session_state.pdf_name}' ({pages} páginas) carregado. Use as abas abaixo para editar.")
        
        # Modo de mesclagem de múltiplos arquivos
        else:
            st.session_state.is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files
            st.info(f"{len(uploaded_files)} arquivos carregados. Vá para a aba 'Mesclar' para continuar.")
        
        # st.rerun() força o script a re-executar com o novo estado atualizado
        st.rerun()

# ------------- CRIAÇÃO DINÂMICA DAS ABAS --------------------
tabs_to_show = []
if st.session_state.get('is_single_pdf_mode', False):
    tabs_to_show.append("Peças Jurídicas")
    if st.session_state.get('visual_tab_enabled', False):
        tabs_to_show.append("Visual")
    tabs_to_show.extend(["Remover", "Extrair", "Dividir", "Otimizar"])

tabs_to_show.append("Mesclar") # A aba Mesclar está sempre disponível

active_tabs = st.tabs(tabs_to_show)
tab_map = {name: tab for name, tab in zip(tabs_to_show, active_tabs)}

# Carrega o documento PDF em cache se estiver no modo de arquivo único
doc_cached = None
if st.session_state.get('is_single_pdf_mode', False):
    doc_cached = get_pdf_document(st.session_state.pdf_doc_bytes_original)
    if not doc_cached:
        st.error("O PDF carregado parece ser inválido ou corrompido. Por favor, carregue outro arquivo.")
        st.stop()
    base_name = os.path.splitext(st.session_state.pdf_name)[0]

# ===========================================================
# RENDERIZAÇÃO DO CONTEÚDO DE CADA ABA
# ===========================================================

if "Mesclar" in tab_map:
    with tab_map["Mesclar"]:
        st.header("🔗 Mesclar Múltiplos PDFs")
        
        files_to_merge_list = st.session_state.get('files_to_merge', [])

        if not files_to_merge_list:
            st.info("Para mesclar, carregue dois ou mais arquivos PDF no campo de upload acima.")
            if st.session_state.get('is_single_pdf_mode'):
                 st.warning("Você está no modo de edição de arquivo único. Para ativar a mesclagem, carregue múltiplos arquivos.")
        else:
            def move_file(i, delta):
                files = st.session_state.files_to_merge
                files[i + delta], files[i] = files[i], files[i + delta]

            st.write("Use os botões ⬆️ e ⬇️ para reordenar os arquivos. A mesclagem seguirá a ordem de cima para baixo.")
            for i, f in enumerate(files_to_merge_list):
                c_up, c_down, c_lbl = st.columns([0.08, 0.08, 0.84])
                if i > 0: c_up.button("⬆️", key=f"up_{i}", on_click=move_file, args=(i, -1))
                # ### BUG CORRIGIDO AQUI ###
                # A chave foi alterada de "dn_{i}" para "down_{i}" para corresponder à lógica de limpeza do estado.
                if i < len(files_to_merge_list) - 1: c_down.button("⬇️", key=f"down_{i}", on_click=move_file, args=(i, 1))
                c_lbl.write(f"**{i + 1}.** {f.name} ({round(f.size / 1_048_576, 2)} MB)")
            
            st.divider()
            col1, col2 = st.columns(2)
            optimize_merge = col1.checkbox("Otimizar PDF resultante", value=True, help="Reduz o tamanho do arquivo final.")
            password_merge = col2.text_input("Senha para o PDF (opcional)", type="password", key="pass_merge")
            
            if st.button("Executar Mesclagem", type="primary"):
                try:
                    with st.spinner("Mesclando arquivos..."):
                        merged_doc = fitz.open()
                        for f_to_merge in st.session_state.files_to_merge:
                            with fitz.open(stream=f_to_merge.getvalue(), filetype="pdf") as src_doc:
                                merged_doc.insert_pdf(src_doc)
                        generate_download_button(merged_doc, "documento_mesclado.pdf", "Baixar PDF Mesclado", {"deflate_images": optimize_merge, "deflate_fonts": optimize_merge}, password_merge)
                except Exception as e:
                    st.error(f"Ocorreu um erro durante a mesclagem: {e}")

# As abas a seguir só são renderizadas se estivermos no modo de arquivo único e o documento for válido
if st.session_state.get('is_single_pdf_mode') and doc_cached:
    if "Peças Jurídicas" in tab_map:
        with tab_map["Peças Jurídicas"]:
            st.header("⚖️ Extrair Peças Jurídicas (por Marcadores)")
            pcs = st.session_state.found_legal_pieces
            if not pcs: 
                st.warning("Nenhuma peça jurídica foi reconhecida automaticamente pelos marcadores (bookmarks) deste PDF.")
                st.info("Dica: Use a aba 'Extrair' ou 'Visual' para selecionar páginas manualmente.")
            else:
                col1, col2, col3 = st.columns(3)
                if col1.button("Selecionar todas as peças"):
                    for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = True
                if col2.button("Limpar seleção de peças"):
                    for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = False
                if col3.button("Restaurar pré-seleção"):
                    for p in pcs: st.session_state[f"legal_piece_{p['unique_id']}"] = p['preselect']
                st.divider()
                with st.container(height=350):
                    for p in pcs:
                        key = f"legal_piece_{p['unique_id']}"
                        if key not in st.session_state: st.session_state[key] = p['preselect']
                        st.checkbox(f"**{p['category']}**: {p['title']} (págs. {p['start_page_0_idx'] + 1}-{p['end_page_0_idx'] + 1})", key=key)
                st.divider()
                col1, col2 = st.columns(2)
                optimize_legal = col1.checkbox("Otimizar PDF", value=True, key="opt_legal")
                password_legal = col2.text_input("Senha para o PDF (opcional)", type="password", key="pass_legal")
                if st.button("Extrair Peças Selecionadas", type="primary"):
                    selected_pages = set()
                    for p in pcs:
                        if st.session_state.get(f"legal_piece_{p['unique_id']}", False):
                            selected_pages.update(range(p['start_page_0_idx'], p['end_page_0_idx'] + 1))
                    if not selected_pages: st.warning("Nenhuma peça foi selecionada para extração.")
                    else:
                        try:
                            with st.spinner("Gerando PDF com as peças selecionadas..."):
                                new_doc = fitz.open()
                                insert_pages(new_doc, doc_cached, sorted(list(selected_pages)))
                                generate_download_button(new_doc, f"{base_name}_pecas.pdf", "Baixar Peças Extraídas", {"deflate_images": optimize_legal, "deflate_fonts": optimize_legal}, password_legal)
                        except Exception as e:
                            st.error(f"Erro ao extrair peças: {e}")

    if "Visual" in tab_map:
        with tab_map["Visual"]:
            st.header("🖼️ Gerenciar Páginas Visualmente")
            st.session_state.page_previews = build_previews(st.session_state.pdf_doc_bytes_original)
            st.sidebar.divider()
            st.sidebar.subheader("Controles Visuais")
            n_cols = st.sidebar.slider("Colunas de visualização", 2, 10, 5, key="visual_cols")
            
            sel_pages_indices = [i for i, v in st.session_state.visual_page_selection.items() if v]
            
            st.sidebar.info(f"**{len(sel_pages_indices)}** de {doc_cached.page_count} páginas selecionadas.")
            c1, c2 = st.sidebar.columns(2)
            
            def select_all_visual():
                for i in range(doc_cached.page_count): st.session_state.visual_page_selection[i] = True
            def clear_all_visual():
                st.session_state.visual_page_selection = {}
            
            c1.button("Selecionar Todas", key="visual_select_all", on_click=select_all_visual)
            c2.button("Limpar Seleção", key="visual_clear_all", on_click=clear_all_visual)
            
            cols = st.columns(n_cols)
            for i, img_bytes in enumerate(st.session_state.page_previews):
                with cols[i % n_cols]:
                    st.image(img_bytes, use_column_width=True, caption=f"Pág. {i+1}")
                    current_value = st.session_state.visual_page_selection.get(i, False)
                    # A atualização do estado da seleção é feita diretamente pelo fluxo do Streamlit
                    st.session_state.visual_page_selection[i] = st.checkbox(f"Selecionar", key=f"select_page_preview_{i}", value=current_value)
            
            st.divider()
            password_visual = st.text_input("Senha para o PDF (opcional)", type="password", key="pass_visual")
            col_del, col_ext = st.columns(2)
            
            if col_del.button("🗑️ Excluir Selecionadas", disabled=not sel_pages_indices):
                if len(sel_pages_indices) >= doc_cached.page_count: st.error("Não é possível excluir todas as páginas do documento.")
                else:
                    try:
                        with st.spinner("Excluindo páginas..."):
                            new_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                            new_doc.delete_pages(sel_pages_indices)
                            generate_download_button(new_doc, f"{base_name}_excluido.pdf", "Baixar PDF Modificado", password=password_visual)
                    except Exception as e:
                        st.error(f"Erro ao excluir páginas: {e}")

            if col_ext.button("✨ Extrair Selecionadas", disabled=not sel_pages_indices):
                try:
                    with st.spinner("Extraindo páginas..."):
                        new_doc = fitz.open()
                        insert_pages(new_doc, doc_cached, sel_pages_indices)
                        generate_download_button(new_doc, f"{base_name}_extraido_visual.pdf", "Baixar PDF Extraído", password=password_visual)
                except Exception as e:
                    st.error(f"Erro ao extrair páginas: {e}")

    if "Remover" in tab_map:
        with tab_map["Remover"]:
            st.header("🗑️ Remover Páginas por Número ou Marcador")
            to_del = set()
            st.subheader("Remover por Marcador")
            bm_term_del = st.text_input("Filtrar marcadores para remover", key="del_bm_filter")
            with st.container(height=200):
                for bm in st.session_state.bookmarks_data:
                    if not bm_term_del or bm_term_del.lower() in bm['display_text'].lower():
                        if st.checkbox(bm['display_text'], key=f"del_{bm['id']}"):
                            to_del.update(range(bm['start_page_0_idx'], bm['end_page_0_idx'] + 1))
            st.subheader("Remover por Número de Página")
            page_numbers_del = st.text_input("Números de página a remover (ex: 1, 3-5, 10)", key="del_nums")
            to_del.update(parse_page_input(page_numbers_del, doc_cached.page_count))
            st.divider()
            col1, col2 = st.columns(2)
            optimize_rem = col1.checkbox("Otimizar PDF", value=True, key="opt_rem")
            password_rem = col2.text_input("Senha para o PDF (opcional)", type="password", key="pass_rem")
            if st.button("Executar Remoção", type="primary", disabled=not to_del):
                if len(to_del) >= doc_cached.page_count: st.error("Não é possível remover todas as páginas.")
                else:
                    try:
                        with st.spinner("Removendo páginas selecionadas..."):
                            new_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                            new_doc.delete_pages(sorted(list(to_del)))
                            output_filename = f"{base_name}_removido.pdf"
                            generate_download_button(new_doc, output_filename, "Baixar PDF Modificado", {"deflate_images": optimize_rem, "deflate_fonts": optimize_rem}, password_rem)
                    except Exception as e:
                        st.error(f"Erro ao remover páginas: {e}")

    if "Extrair" in tab_map:
        with tab_map["Extrair"]:
            st.header("✨ Extrair Páginas por Número ou Marcador")
            to_ext = set()
            st.subheader("Extrair por Marcador")
            bm_term_ext = st.text_input("Filtrar marcadores para extrair", key="ext_bm_filter")
            with st.container(height=200):
                for bm in st.session_state.bookmarks_data:
                    if not bm_term_ext or bm_term_ext.lower() in bm['display_text'].lower():
                        if st.checkbox(bm['display_text'], key=f"ext_{bm['id']}"):
                            to_ext.update(range(bm['start_page_0_idx'], bm['end_page_0_idx'] + 1))
            st.subheader("Extrair por Número de Página")
            page_numbers_ext = st.text_input("Números de página a extrair (ex: 1, 3-5, 10)", key="ext_nums")
            to_ext.update(parse_page_input(page_numbers_ext, doc_cached.page_count))
            st.divider()
            col1, col2 = st.columns(2)
            optimize_ext = col1.checkbox("Otimizar PDF", value=True, key="opt_ext")
            password_ext = col2.text_input("Senha para o PDF (opcional)", type="password", key="pass_ext")
            if st.button("Executar Extração", type="primary", disabled=not to_ext):
                try:
                    with st.spinner("Extraindo páginas selecionadas..."):
                        new_doc = fitz.open()
                        insert_pages(new_doc, doc_cached, sorted(list(to_ext)))
                        output_filename = f"{base_name}_extraido.pdf"
                        generate_download_button(new_doc, output_filename, "Baixar PDF Extraído", {"deflate_images": optimize_ext, "deflate_fonts": optimize_ext}, password_ext)
                except Exception as e:
                    st.error(f"Erro ao extrair páginas: {e}")

    if "Dividir" in tab_map:
        with tab_map["Dividir"]:
            st.header("🔪 Dividir PDF em Múltiplas Partes")
            mode = st.radio("Método de Divisão", ("A cada N páginas", "Por tamanho máximo (MB)"), horizontal=True)
            optimize_split = st.checkbox("Otimizar partes ao salvar", value=True, key="opt_split")
            if mode == "A cada N páginas":
                n_pages = st.number_input("Número de páginas por parte", min_value=1, value=10, step=1)
                if st.button("Dividir por Número de Páginas", type="primary"):
                    try:
                        with st.spinner(f"Dividindo o PDF a cada {n_pages} páginas..."):
                            parts_data = []
                            for i in range(0, doc_cached.page_count, n_pages):
                                part_doc = fitz.open()
                                page_range = list(range(i, min(i + n_pages, doc_cached.page_count)))
                                insert_pages(part_doc, doc_cached, page_range)
                                part_buffer = part_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize_split, deflate_fonts=optimize_split)
                                parts_data.append((f"{base_name}_parte_{i//n_pages + 1}.pdf", part_buffer))
                                part_doc.close()
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for name, data in parts_data: zf.writestr(name, data)
                            st.download_button("⬇️ Baixar ZIP com as Partes", zip_buffer.getvalue(), f"{base_name}_partes.zip", "application/zip")
                            st.success(f"PDF dividido em {len(parts_data)} partes.")
                    except Exception as e:
                        st.error(f"Erro ao dividir por número de páginas: {e}")
            else:
                max_mb = st.number_input("Tamanho máximo por parte (MB)", min_value=0.5, value=5.0, step=0.1)
                if st.button("Dividir por Tamanho", type="primary"):
                    try:
                        with st.spinner(f"Dividindo o PDF em partes de até {max_mb} MB... (Isso pode ser demorado)"):
                            parts_data = []
                            max_bytes = max_mb * 1024 * 1024
                            current_part_doc = fitz.open()
                            for p_num in range(doc_cached.page_count):
                                current_part_doc.insert_pdf(doc_cached, from_page=p_num, to_page=p_num)
                                temp_buffer = current_part_doc.tobytes(garbage=1, deflate=True)
                                if len(temp_buffer) > max_bytes and current_part_doc.page_count > 1:
                                    final_part_doc = fitz.open()
                                    final_part_doc.insert_pdf(current_part_doc, from_page=0, to_page=current_part_doc.page_count - 2)
                                    final_buffer = final_part_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize_split, deflate_fonts=optimize_split)
                                    parts_data.append((f"{base_name}_parte_{len(parts_data) + 1}.pdf", final_buffer))
                                    final_part_doc.close()
                                    last_page_doc = fitz.open()
                                    last_page_doc.insert_pdf(current_part_doc, from_page=current_part_doc.page_count - 1, to_page=current_part_doc.page_count - 1)
                                    current_part_doc.close()
                                    current_part_doc = last_page_doc
                            if current_part_doc.page_count > 0:
                                final_buffer = current_part_doc.tobytes(garbage=3, deflate=True, clean=True, deflate_images=optimize_split, deflate_fonts=optimize_split)
                                parts_data.append((f"{base_name}_parte_{len(parts_data) + 1}.pdf", final_buffer))
                            current_part_doc.close()
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for name, data in parts_data: zf.writestr(name, data)
                            st.download_button("⬇️ Baixar ZIP com as Partes", zip_buffer.getvalue(), f"{base_name}_partes_por_tamanho.zip", "application/zip")
                            st.success(f"PDF dividido em {len(parts_data)} partes.")
                    except Exception as e:
                        st.error(f"Erro ao dividir por tamanho: {e}")

    if "Otimizar" in tab_map:
        with tab_map["Otimizar"]:
            st.header("🚀 Otimizar PDF para Reduzir Tamanho")
            st.write("Reduza o tamanho do arquivo do seu PDF. A otimização 'Máxima' pode afetar a qualidade das imagens.")
            profile = st.selectbox("Perfil de Otimização", ("Leve", "Recomendada", "Máxima"), index=1)
            password_opt = st.text_input("Senha para o PDF (opcional)", type="password", key="pass_opt")
            if st.button("Otimizar Agora", type="primary"):
                try:
                    with st.spinner("Otimizando PDF..."):
                        opt_options = {}
                        if profile == "Leve": opt_options.update(garbage=2, deflate=True)
                        elif profile == "Recomendada": opt_options.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
                        elif profile == "Máxima": opt_options.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, linear=True, clean=True)
                        doc_to_optimize = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                        output_filename = f"{base_name}_otimizado.pdf"
                        generate_download_button(doc_to_optimize, output_filename, "Baixar PDF Otimizado", opt_options, password_opt)
                except Exception as e:
                    st.error(f"Erro ao otimizar o PDF: {e}")
