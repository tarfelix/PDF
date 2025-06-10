"""
pdf_editor_ptbr_streamlit.py
Editor e Divisor de PDF Completo (PT-BR) – Versão Refatorada e Aprimorada
-------------------------------------------------------------------------
• Compatibilidade com PyMuPDF ≥ 1.23 (parâmetro subpages)
• Helper insert_pages() retro-compatível (pages/subpages)
• @st.cache_resource para documento PDF e miniaturas para alta performance
• Lógica de "Dividir por Tamanho" otimizada para evitar lentidão
• Função centralizada generate_download_button() para evitar repetição de código
• Feedback visual com st.spinner em todas as operações demoradas
• Nomes de arquivo de saída dinâmicos baseados no original
• Tratamento de erros com try/except para uma experiência mais robusta
• Nova funcionalidade: Proteção de PDFs com senha
• Interface da aba "Visual" aprimorada com mais controles
"""

# ===========================================================
# IMPORTS E CONFIGURAÇÃO
# ===========================================================
import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
import os
import copy
from unidecode import unidecode

st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF Completo (PT-BR)")


# ===========================================================
# FUNÇÕES AUXILIARES E DE COMPATIBILIDADE
# ===========================================================

def insert_pages(dst: fitz.Document, src: fitz.Document, pages: list[int]):
    """Insere lista de páginas 0-based de *src* em *dst* sem falhar em versões antigas."""
    try:
        dst.insert_pdf(src, subpages=pages)  # ≥ 1.23
    except TypeError:
        try:
            dst.insert_pdf(src, pages=pages)  # 1.19 – 1.22
        except TypeError:
            # fallback: página a página
            for p in pages:
                dst.insert_pdf(src, from_page=p, to_page=p)

def generate_download_button(doc_to_save, filename, button_text, optimize_options=None, password=""):
    """Salva um documento PDF em memória e gera um botão de download, com opção de senha."""
    if optimize_options is None:
        optimize_options = {}

    save_opts = dict(garbage=4, deflate=True, clean=True, **optimize_options)
    
    # Adiciona criptografia se uma senha for fornecida
    if password:
        save_opts.update({
            "encryption": fitz.ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
            "permissions": fitz.PERM_PRINT | fitz.PERM_COPY | fitz.PERM_ANNOTATE
        })

    try:
        buf = doc_to_save.tobytes(**save_opts)
        doc_to_save.close()
        
        st.download_button(
            label=f"⬇️ {button_text}",
            data=buf,
            file_name=filename,
            mime="application/pdf",
        )
        st.success(f"Seu arquivo '{filename}' está pronto para download!")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo para download: {e}")

# ===========================================================
# ESTADO DA SESSÃO
# ===========================================================
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'last_uploaded_file_ids': [], 'page_previews': [], 'visual_page_selection': {},
    'files_to_merge': [], 'found_legal_pieces': [],
}

def initialize_session_state():
    """Reseta seletivamente o estado da aplicação, limpando chaves dinâmicas."""
    dyn_keys = [k for k in st.session_state.keys() if k.startswith((
        "delete_bookmark_", "extract_bookmark_", "select_page_preview_", "legal_piece_", "up_", "down_")) or
        k.endswith(("_input", "_checkbox"))]
    for k in dyn_keys:
        st.session_state.pop(k, None)
    
    # Recria os defaults
    for k, v in DEFAULT_STATE.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(v)

if 'initialized_once' not in st.session_state:
    initialize_session_state()
    st.session_state.initialized_once = True

# ===========================================================
# PALAVRAS-CHAVE JURÍDICAS
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
    "Defesa/Contestação", "Réplica", "Recurso", "Ata de Audiência",
    "Laudo", "Manifestação"
]

# ===========================================================
# FUNÇÕES DE PDF CACHEADAS
# ===========================================================
@st.cache_resource(show_spinner="Gerando miniaturas do PDF...")
def build_previews(pdf_bytes: bytes, dpi=48):
    """Gera miniaturas PNG de todas as páginas."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        mtx = fitz.Matrix(dpi / 72, dpi / 72)
        return [pg.get_pixmap(matrix=mtx).tobytes("png") for pg in doc]

@st.cache_data(max_entries=5, show_spinner="Analisando metadados do PDF...")
def get_pdf_metadata(pdf_bytes: bytes, name="pdf"):
    """Retorna (bookmarks, n_pages, erro) de um PDF em bytes."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            bms = get_bookmark_ranges(d)
            return bms, d.page_count, None
    except Exception as e:
        return [], 0, f"Erro ao ler {name}: {e}"

@st.cache_resource(show_spinner="Carregando documento PDF...")
def get_pdf_document(_pdf_bytes):
    """Abre o documento PDF a partir dos bytes e o mantém em cache."""
    if not _pdf_bytes:
        return None
    try:
        return fitz.open(stream=_pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Não foi possível abrir o PDF: {e}")
        return None

def get_bookmark_ranges(doc: fitz.Document):
    """Converte TOC em lista de dicionários com intervalo de páginas."""
    toc = doc.get_toc(simple=False)
    res = []
    total = doc.page_count
    for i, (lvl, title, page1, *_) in enumerate(toc):
        if not 1 <= page1 <= total:
            continue
        start0 = page1 - 1
        end0 = total - 1
        for j in range(i + 1, len(toc)):
            lvl_j, _, page_j, *_ = toc[j]
            if lvl_j <= lvl:
                end0 = page_j - 2
                break
        end0 = max(start0, min(end0, total - 1))
        disp = f"{'➡️' * (lvl - 1)}{'↪️' if lvl > 1 else ''} {title} (Págs. {start0 + 1}-{end0 + 1})"
        res.append({
            "id": f"bm_{i}_{page1}", "level": lvl, "title": title,
            "start_page_0_idx": start0, "end_page_0_idx": end0, "display_text": disp,
        })
    return res

def find_legal_sections(bms):
    """Classifica marcadores em categorias jurídicas."""
    out = []
    for i, bm in enumerate(bms):
        norm = unidecode(bm['title']).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({**bm,
                            'category': cat,
                            'unique_id': f"legal_{i}_{bm['id']}",
                            'preselect': cat in PRE_SELECTED_LEGAL_CATEGORIES})
                break
    return out

def parse_page_input(inp: str, max1: int):
    """Converte input tipo '1,3-5' em lista de índices 0-based."""
    sel = set()
    if not inp:
        return []
    for part in inp.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if '-' in part:
                a, b = map(int, part.split('-'))
                if a > b: a, b = b, a
                sel.update(i - 1 for i in range(a, b + 1) if 1 <= i <= max1)
            else:
                p = int(part)
                if 1 <= p <= max1:
                    sel.add(p - 1)
        except ValueError:
            st.warning(f"Entrada inválida: '{part}'")
    return sorted(list(sel))

# ===========================================================
# INTERFACE PRINCIPAL
# ===========================================================
st.title("✂️ Editor e Divisor de PDF Completo (PT-BR)")
st.markdown("Carregue um ou mais PDFs e escolha a ação desejada nas abas. As funcionalidades foram aprimoradas com **proteção por senha**, **melhor performance** e **feedback visual**.")

st.sidebar.button("🔄 Limpar Tudo e Recomeçar", on_click=initialize_session_state, type="primary")

uploaded_files = st.file_uploader("📄 Carregue seu(s) PDF(s) aqui", type="pdf", accept_multiple_files=True)

doc_cached = None
is_single_pdf_mode = False

# ---------------- Processa o upload -----------------
if uploaded_files:
    file_ids = sorted(f.file_id for f in uploaded_files)
    if file_ids != st.session_state.last_uploaded_file_ids:
        initialize_session_state()
        st.session_state.last_uploaded_file_ids = file_ids

        if len(uploaded_files) == 1:
            is_single_pdf_mode = True
            uploaded_file = uploaded_files[0]
            st.session_state.pdf_doc_bytes_original = uploaded_file.getvalue()
            st.session_state.pdf_name = uploaded_file.name
            
            bms, pages, err = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, uploaded_file.name)
            if err:
                st.error(err)
                is_single_pdf_mode = False
            else:
                st.session_state.bookmarks_data = bms
                st.session_state.found_legal_pieces = find_legal_sections(bms)
                st.info(f"PDF '{st.session_state.pdf_name}' ({pages} páginas) carregado. Escolha uma ação abaixo.")
        else:
            is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files
            st.info(f"{len(uploaded_files)} arquivos carregados e prontos para a aba 'Mesclar'.")
        
        st.rerun()

elif st.session_state.pdf_doc_bytes_original:
    is_single_pdf_mode = True

if is_single_pdf_mode:
    doc_cached = get_pdf_document(st.session_state.pdf_doc_bytes_original)
    if not doc_cached:
        st.error("O PDF carregado parece ser inválido ou corrompido. Por favor, carregue outro arquivo.")
        st.stop()
    base_name = os.path.splitext(st.session_state.pdf_name)[0]

# ------------- Abas Dinâmicas --------------------
tabs_to_show = ["Mesclar"]
if is_single_pdf_mode:
    tabs_to_show = ["Peças Jurídicas", "Visual", "Remover", "Extrair", "Dividir", "Otimizar", "Mesclar"]

active_tabs = st.tabs(tabs_to_show)
tab_map = {name: tab for name, tab in zip(tabs_to_show, active_tabs)}

# ===========================================================
# ABA MESCLAR
# ===========================================================
with tab_map["Mesclar"]:
    st.header("🔗 Mesclar Múltiplos PDFs")
    
    files_to_merge = st.session_state.get('files_to_merge', [])
    if not files_to_merge and not is_single_pdf_mode:
        st.info("Para mesclar, carregue dois ou mais arquivos PDF no campo de upload acima.")
    elif not files_to_merge and is_single_pdf_mode:
        st.warning("Você carregou apenas um arquivo. Para mesclar, carregue múltiplos arquivos.")
    else:
        def move_file(i, delta):
            lst = st.session_state.files_to_merge
            lst[i + delta], lst[i] = lst[i], lst[i + delta]

        for i, f in enumerate(files_to_merge):
            c_up, c_down, c_lbl = st.columns([0.08, 0.08, 0.84])
            if i > 0: c_up.button("⬆️", key=f"up_{i}", on_click=move_file, args=(i, -1))
            if i < len(files_to_merge) - 1: c_down.button("⬇️", key=f"dn_{i}", on_click=move_file, args=(i, 1))
            c_lbl.write(f"**{i + 1}.** {f.name} ({round(f.size / 1_048_576, 2)} MB)")

        st.divider()
        col1, col2 = st.columns(2)
        optimize_merge = col1.checkbox("Otimizar PDF resultante", value=True, help="Reduz o tamanho do arquivo final.")
        password_merge = col2.text_input("Senha para o PDF (opcional)", type="password", key="pass_merge")

        if st.button("Executar Mesclagem", type="primary"):
            try:
                with st.spinner("Mesclando arquivos..."):
                    merged_doc = fitz.open()
                    for f in files_to_merge:
                        with fitz.open(stream=f.getvalue(), filetype="pdf") as src_doc:
                            merged_doc.insert_pdf(src_doc)
                    
                    generate_download_button(
                        merged_doc, "documento_mesclado.pdf", "Baixar PDF Mesclado",
                        {"deflate_images": optimize_merge, "deflate_fonts": optimize_merge},
                        password_merge
                    )
            except Exception as e:
                st.error(f"Ocorreu um erro durante a mesclagem: {e}")


# ===========================================================
# ABAS DE ARQUIVO ÚNICO
# ===========================================================
if is_single_pdf_mode and doc_cached:

    with tab_map["Peças Jurídicas"]:
        st.header("⚖️ Extrair Peças Jurídicas (por Marcadores)")
        pcs = st.session_state.found_legal_pieces
        if not pcs:
            st.warning("Nenhuma peça jurídica foi reconhecida automaticamente pelos marcadores (bookmarks) deste PDF.")
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
                    if key not in st.session_state:
                        st.session_state[key] = p['preselect']
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
                
                if not selected_pages:
                    st.warning("Nenhuma peça foi selecionada para extração.")
                else:
                    try:
                        with st.spinner("Gerando PDF com as peças selecionadas..."):
                            new_doc = fitz.open()
                            insert_pages(new_doc, doc_cached, sorted(list(selected_pages)))
                            output_filename = f"{base_name}_pecas_selecionadas.pdf"
                            generate_download_button(
                                new_doc, output_filename, "Baixar Peças Extraídas",
                                {"deflate_images": optimize_legal, "deflate_fonts": optimize_legal},
                                password_legal
                            )
                    except Exception as e:
                        st.error(f"Erro ao extrair peças: {e}")

    with tab_map["Visual"]:
        st.header("🖼️ Gerenciar Páginas Visualmente")
        st.session_state.page_previews = build_previews(st.session_state.pdf_doc_bytes_original)

        # Controles na sidebar
        st.sidebar.divider()
        st.sidebar.subheader("Controles Visuais")
        n_cols = st.sidebar.slider("Colunas de visualização", 2, 10, 5, key="visual_cols")
        
        sel_pages = [i for i, v in st.session_state.visual_page_selection.items() if v]
        st.sidebar.info(f"**{len(sel_pages)}** de {doc_cached.page_count} páginas selecionadas.")

        c1, c2 = st.sidebar.columns(2)
        if c1.button("Selecionar Todas", key="visual_select_all"):
            for i in range(doc_cached.page_count): st.session_state.visual_page_selection[i] = True
            st.rerun()
        if c2.button("Limpar Seleção", key="visual_clear_all"):
            for i in range(doc_cached.page_count): st.session_state.visual_page_selection[i] = False
            st.rerun()
        
        # Display das páginas
        cols = st.columns(n_cols)
        for i, img_bytes in enumerate(st.session_state.page_previews):
            with cols[i % n_cols]:
                st.image(img_bytes, use_column_width=True)
                key = f"select_page_preview_{i}"
                if key not in st.session_state:
                     st.session_state[key] = st.session_state.visual_page_selection.get(i, False)
                
                st.session_state.visual_page_selection[i] = st.checkbox(f"Pág. {i + 1}", key=key, value=st.session_state.visual_page_selection.get(i, False))

        st.divider()
        st.subheader("Ações com as páginas selecionadas")
        password_visual = st.text_input("Senha para o PDF (opcional)", type="password", key="pass_visual")
        
        col_del, col_ext = st.columns(2)
        if col_del.button("🗑️ Excluir Selecionadas", disabled=not sel_pages):
            if len(sel_pages) >= doc_cached.page_count:
                st.error("Não é possível excluir todas as páginas do documento.")
            else:
                try:
                    with st.spinner("Excluindo páginas..."):
                        new_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                        new_doc.delete_pages(sel_pages)
                        output_filename = f"{base_name}_paginas_excluidas.pdf"
                        generate_download_button(
                            new_doc, output_filename, "Baixar PDF Modificado",
                            password=password_visual
                        )
                except Exception as e:
                    st.error(f"Erro ao excluir páginas: {e}")

        if col_ext.button("✨ Extrair Selecionadas", disabled=not sel_pages):
            try:
                with st.spinner("Extraindo páginas..."):
                    new_doc = fitz.open()
                    insert_pages(new_doc, doc_cached, sel_pages)
                    output_filename = f"{base_name}_paginas_extraidas.pdf"
                    generate_download_button(
                        new_doc, output_filename, "Baixar PDF Extraído",
                        password=password_visual
                    )
            except Exception as e:
                st.error(f"Erro ao extrair páginas: {e}")

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
            if len(to_del) >= doc_cached.page_count:
                st.error("Não é possível remover todas as páginas.")
            else:
                try:
                    with st.spinner("Removendo páginas selecionadas..."):
                        new_doc = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                        new_doc.delete_pages(sorted(list(to_del)))
                        output_filename = f"{base_name}_removido.pdf"
                        generate_download_button(
                            new_doc, output_filename, "Baixar PDF Modificado",
                            {"deflate_images": optimize_rem, "deflate_fonts": optimize_rem},
                            password_rem
                        )
                except Exception as e:
                    st.error(f"Erro ao remover páginas: {e}")

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
                    generate_download_button(
                        new_doc, output_filename, "Baixar PDF Extraído",
                        {"deflate_images": optimize_ext, "deflate_fonts": optimize_ext},
                        password_ext
                    )
            except Exception as e:
                st.error(f"Erro ao extrair páginas: {e}")

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
                            for name, data in parts_data:
                                zf.writestr(name, data)
                        
                        st.download_button("⬇️ Baixar ZIP com as Partes", zip_buffer.getvalue(), f"{base_name}_partes.zip", "application/zip")
                        st.success(f"PDF dividido em {len(parts_data)} partes.")

                except Exception as e:
                    st.error(f"Erro ao dividir por número de páginas: {e}")

        else: # Por tamanho
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
                            for name, data in parts_data:
                                zf.writestr(name, data)
                        
                        st.download_button("⬇️ Baixar ZIP com as Partes", zip_buffer.getvalue(), f"{base_name}_partes_por_tamanho.zip", "application/zip")
                        st.success(f"PDF dividido em {len(parts_data)} partes.")

                except Exception as e:
                    st.error(f"Erro ao dividir por tamanho: {e}")

    with tab_map["Otimizar"]:
        st.header("🚀 Otimizar PDF para Reduzir Tamanho")
        st.write("Reduza o tamanho do arquivo do seu PDF. A otimização 'Máxima' pode afetar a qualidade das imagens.")
        profile = st.selectbox("Perfil de Otimização", ("Leve", "Recomendada", "Máxima"), index=1)
        
        password_opt = st.text_input("Senha para o PDF (opcional)", type="password", key="pass_opt")

        if st.button("Otimizar Agora", type="primary"):
            try:
                with st.spinner("Otimizando PDF..."):
                    opt_options = {}
                    if profile == "Leve":
                        opt_options.update(garbage=2, deflate=True)
                    elif profile == "Recomendada":
                        opt_options.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True)
                    elif profile == "Máxima":
                        opt_options.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, linear=True, clean=True)
                    
                    # Para otimização, trabalhamos com uma cópia para não alterar o doc cacheado
                    doc_to_optimize = fitz.open(stream=st.session_state.pdf_doc_bytes_original)
                    output_filename = f"{base_name}_otimizado.pdf"
                    generate_download_button(
                        doc_to_optimize, output_filename, "Baixar PDF Otimizado",
                        opt_options, password_opt
                    )
            except Exception as e:
                st.error(f"Erro ao otimizar o PDF: {e}")
