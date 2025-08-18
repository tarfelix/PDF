# ===========================================================
# Editor e Divisor de PDF Completo (PT-BR) — Versão 3
# ===========================================================
# Recursos:
# - Visual: reordenar páginas selecionadas (⬆️/⬇️), extrair na ordem e reordenar o doc inteiro.
# - Exportar por QUALQUER marcador (nível filtrável), com nomes automáticos (slug).
# - Perfil corporativo: paleta azul, cabeçalho com logo (URL) e modo Alto Contraste (toggle).
# - Compatibilidade PyMuPDF (fallbacks) e limpeza opcional de metadados/anotações.
# ===========================================================

import streamlit as st
import fitz  # PyMuPDF
import io, zipfile, os, copy, re
from typing import List, Optional
from unidecode import unidecode

# ---- Identidade visual (ajustável na UI) ----
DEFAULT_BRAND = {
    "name": "Soares, Picon Sociedade de Advogados",
    "primary": "#0F3D73",
    "secondary": "#1E5AA7",
    "accent": "#2E7DFF",
    "bg_light": "#E9F2FB",
    "bg_dark": "#0B0F14",
    "text_dark": "#0B0F14",
    "text_light": "#F8FAFC",
    "logo_url": "",  # cole aqui a URL do logo (PNG/SVG) do site
    "subtitle": "Mais de 50 anos de atuação na advocacia consultiva e contenciosa",
}

st.set_page_config(layout="wide", page_title="Editor e Divisor de PDF — v3")
VISUAL_PREVIEW_SIZE_LIMIT_MB = 50

# Fallbacks de encriptação/permissões entre versões do PyMuPDF
ENCRYPT_AES_256 = getattr(fitz, "ENCRYPT_AES_256", getattr(fitz, "PDF_ENCRYPT_AES_256", 0))
PERM_PRINT      = getattr(fitz, "PERM_PRINT",      getattr(fitz, "PDF_PERM_PRINT",      0))
PERM_COPY       = getattr(fitz, "PERM_COPY",       getattr(fitz, "PDF_PERM_COPY",       0))
PERM_ANNOTATE   = getattr(fitz, "PERM_ANNOTATE",   getattr(fitz, "PDF_PERM_ANNOTATE",   0))

# ---------- helpers ----------
def safe_slug(text: str, maxlen: int = 60) -> str:
    s = unidecode(text).strip().lower()
    s = re.sub(r"[^a-z0-9\-\_\s\.]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return (s or "arquivo")[:maxlen]

def insert_pages(dst: fitz.Document, src: fitz.Document, pages: List[int]):
    try:
        dst.insert_pdf(src, subpages=pages)
    except TypeError:
        try:
            dst.insert_pdf(src, pages=pages)
        except TypeError:
            for p in pages:
                dst.insert_pdf(src, from_page=p, to_page=p)

def generate_download_button(
    doc_to_save: fitz.Document,
    filename: str,
    button_text: str,
    optimize_options: Optional[dict] = None,
    password: str = "",
    permissions: Optional[int] = None,
    remove_metadata: bool = False,
    remove_annotations: bool = False,
):
    if optimize_options is None:
        optimize_options = {}
    # limpeza opcional
    if remove_annotations:
        try:
            for page in doc_to_save:
                ann = page.first_annot
                while ann:
                    nxt = ann.next
                    page.delete_annot(ann)
                    ann = nxt
        except Exception:
            pass
    if remove_metadata:
        try: doc_to_save.set_metadata({})
        except Exception: pass

    save_opts = dict(garbage=4, deflate=True, clean=True, **optimize_options)
    if password:
        if permissions is None:
            permissions = PERM_PRINT | PERM_COPY | PERM_ANNOTATE
        save_opts.update({
            "encryption": ENCRYPT_AES_256,
            "user_pw": password,
            "owner_pw": password,
            "permissions": permissions
        })
    try:
        buf = doc_to_save.tobytes(**save_opts)
        doc_to_save.close()
        st.download_button(f"⬇️ {button_text}", buf, file_name=filename, mime="application/pdf")
        st.success(f"Arquivo pronto: {filename}")
    except Exception as e:
        st.error(f"Erro ao gerar arquivo: {e}")

def inject_brand_css(brand: dict, high_contrast: bool):
    if high_contrast:
        bg_from, bg_to, txt, accent = brand["bg_dark"], "#000000", brand["text_light"], brand["accent"]
    else:
        bg_from, bg_to, txt, accent = brand["primary"], brand["secondary"], brand["text_light"], brand["accent"]
    st.markdown(f"""
    <style>
      .sp-header {{
        display:flex; align-items:center; gap:1rem;
        padding: .75rem 1rem; border-radius: 10px;
        background: linear-gradient(90deg, {bg_from}, {bg_to});
        color:{txt}; margin-bottom:.6rem;
      }}
      .sp-header img {{ height:48px; width:auto; border-radius:6px; }}
      .sp-hgroup {{ display:flex; flex-direction:column; line-height:1.1; }}
      .sp-title {{ font-weight:700; font-size:1.05rem; }}
      .sp-subtitle {{ font-size:.85rem; opacity:.9; }}
      .sp-badge {{ font-size:.75rem; padding:.1rem .4rem; border-radius:6px; background:{accent}22; color:{txt}; }}
    </style>
    """, unsafe_allow_html=True)

def brand_header(brand: dict, high_contrast: bool):
    inject_brand_css(brand, high_contrast)
    logo_html = f'<img src="{brand["logo_url"]}" alt="Logo" />' if brand.get("logo_url") else ""
    st.markdown(f"""
    <div class="sp-header">
      {logo_html}
      <div class="sp-hgroup">
        <div class="sp-title">{brand["name"]} <span class="sp-badge">Ferramentas PDF</span></div>
        <div class="sp-subtitle">{brand.get("subtitle","")}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ---------- estado ----------
DEFAULT_STATE = {
    'pdf_doc_bytes_original': None, 'pdf_name': None, 'bookmarks_data': [],
    'last_uploaded_file_ids': [], 'page_previews': [],
    'visual_page_selection': {}, 'visual_custom_order': [],
    'files_to_merge': [], 'found_legal_pieces': [],
    'is_single_pdf_mode': False, 'visual_tab_enabled': False,
    'brand': DEFAULT_BRAND.copy(), 'brand_high_contrast': False, 'show_logo': True,
}

def initialize_session_state():
    dyn = [k for k in st.session_state.keys()
           if k.startswith(("delete_bookmark_","extract_bookmark_","select_page_preview_",
                            "legal_piece_","marker_piece_","up_","down_","reord_"))
           or k.endswith(("_input","_checkbox"))]
    for k in dyn: st.session_state.pop(k, None)
    for k,v in DEFAULT_STATE.items():
        st.session_state[k] = DEFAULT_BRAND.copy() if k=="brand" else copy.deepcopy(v)

def _file_key(f):
    if hasattr(f, "file_id"): return f.file_id
    if hasattr(f, "id"): return f.id
    return f"{getattr(f,'name','arquivo')}-{getattr(f,'size',0)}"

if 'initialized_once' not in st.session_state:
    initialize_session_state()
    st.session_state.initialized_once = True

# ---------- cache ----------
LEGAL_KEYWORDS = {
    "Petição Inicial": ['petição inicial','inicial'],
    "Defesa/Contestação": ['defesa','contestação','contestacao'],
    "Réplica": ['réplica','replica','impugnação à contestação','impugnacao a contestacao'],
    "Sentença": ['sentença','sentenca'],
    "Acórdão": ['acórdão','acordao'],
    "Decisão": ['decisão','decisao','decisão interlocutória','decisao interlocutoria'],
    "Despacho": ['despacho'],
    "Recurso": ['recurso','agravo','embargos','apelação','apelacao'],
    "Ata de Audiência": ['ata de audiência','ata de audiencia','termo de audiência','termo de audiencia'],
    "Laudo": ['laudo','parecer técnico','parecer tecnico'],
    "Manifestação": ['manifestação','manifestacao','petição','peticao'],
    "Documento": ['documento'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice','indice','sumário','sumario'],
}
PRE_SELECTED = ["Petição Inicial","Sentença","Acórdão","Decisão","Despacho",
                "Defesa/Contestação","Réplica","Recurso","Ata de Audiência","Laudo","Manifestação"]

@st.cache_resource(show_spinner="Gerando miniaturas...")
def build_previews(pdf_bytes: bytes, dpi=48):
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [pg.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72)).tobytes("png") for pg in doc]

@st.cache_data(max_entries=5, show_spinner="Lendo sumário...")
def get_pdf_metadata(pdf_bytes: bytes, name="pdf"):
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            return get_bookmark_ranges(d), d.page_count, None
    except Exception as e:
        return [], 0, f"Erro ao ler {name}: {e}"

@st.cache_resource(show_spinner="Abrindo PDF...")
def get_pdf_document(_pdf_bytes):
    if not _pdf_bytes: return None
    try:
        return fitz.open(stream=_pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Não foi possível abrir o PDF: {e}")
        return None

def get_bookmark_ranges(doc: fitz.Document):
    toc = doc.get_toc(simple=False)
    res = []
    for i, (lvl, title, page1, *_) in enumerate(toc):
        if not 1 <= page1 <= doc.page_count: continue
        start0, end0 = page1 - 1, doc.page_count - 1
        for j in range(i+1, len(toc)):
            if toc[j][0] <= lvl:
                end0 = toc[j][2] - 2
                break
        end0 = max(start0, min(end0, doc.page_count - 1))
        disp = f"{'➡️'*(lvl-1)}{'↪️' if lvl>1 else ''} {title} (Págs. {start0+1}-{end0+1})"
        res.append({"id": f"bm_{i}_{page1}","display_text": disp,"start_page_0_idx": start0,
                    "end_page_0_idx": end0,"title": title,"level": lvl})
    return res

def find_legal_sections(bms):
    out = []
    for i, bm in enumerate(bms):
        norm = unidecode(bm['title']).lower()
        for cat, kws in LEGAL_KEYWORDS.items():
            if any(unidecode(k).lower() in norm for k in kws):
                out.append({**bm, 'category': cat, 'unique_id': f"legal_{i}_{bm['id']}", 'preselect': cat in PRE_SELECTED})
                break
    return out

def parse_page_input(inp: str, max1: int):
    sel = set()
    if not inp: return []
    for part in inp.split(','):
        part = part.strip()
        try:
            if '-' in part:
                a, b = map(int, part.split('-')); 
                if a>b: a,b=b,a
                sel.update(i-1 for i in range(a,b+1) if 1<=i<=max1)
            else:
                p = int(part)
                if 1<=p<=max1: sel.add(p-1)
        except ValueError:
            st.warning(f"Entrada inválida ignorada: '{part}'")
    return sorted(sel)

# ---------- Sidebar (Aparência + Reset) ----------
with st.sidebar:
    st.subheader("🎨 Aparência")
    st.session_state.brand_high_contrast = st.toggle("Modo alto contraste", value=st.session_state.get('brand_high_contrast', False))
    st.session_state.show_logo = st.checkbox("Mostrar logo no topo", value=st.session_state.get('show_logo', True))
    with st.expander("Identidade Visual (cores/logo)"):
        brand = st.session_state.get('brand', DEFAULT_BRAND.copy())
        brand['name'] = st.text_input("Nome (header)", value=brand.get('name', DEFAULT_BRAND['name']))
        brand['logo_url'] = st.text_input("URL do logo (PNG/SVG)", value=brand.get('logo_url', DEFAULT_BRAND['logo_url']))
        c1,c2 = st.columns(2)
        brand['primary'] = c1.color_picker("Primária", brand.get('primary', DEFAULT_BRAND['primary']))
        brand['secondary'] = c2.color_picker("Secundária", brand.get('secondary', DEFAULT_BRAND['secondary']))
        c3,c4 = st.columns(2)
        brand['accent'] = c3.color_picker("Acento", brand.get('accent', DEFAULT_BRAND['accent']))
        brand['bg_light'] = c4.color_picker("Fundo claro", brand.get('bg_light', DEFAULT_BRAND['bg_light']))
        brand['subtitle'] = st.text_input("Subtítulo", value=brand.get('subtitle', DEFAULT_BRAND['subtitle']))
        st.session_state.brand = brand
    st.divider()
    st.button("🔄 Limpar Tudo e Recomeçar", on_click=initialize_session_state, type="primary")
    st.caption("Dica: proteja o PDF com senha nas operações que oferecem este campo.")

# ---------- Header ----------
brand_header(st.session_state.brand, st.session_state.brand_high_contrast)

st.title("✂️ Editor e Divisor de PDF — v3")
st.write("Carregue um ou mais PDFs. Arquivos **> 50 MB** desativam a aba **Visual** (miniaturas).")

uploaded_files = st.file_uploader("📄 Carregue seu(s) PDF(s)", type="pdf", accept_multiple_files=True)

# ---------- Upload / Estado ----------
if uploaded_files:
    file_ids = sorted(_file_key(f) for f in uploaded_files)
    if file_ids != st.session_state.last_uploaded_file_ids:
        initialize_session_state()
        st.session_state.last_uploaded_file_ids = file_ids
        if len(uploaded_files) == 1:
            st.session_state.is_single_pdf_mode = True
            f = uploaded_files[0]
            size_mb = f.size / (1024*1024)
            st.session_state.visual_tab_enabled = size_mb <= VISUAL_PREVIEW_SIZE_LIMIT_MB
            if not st.session_state.visual_tab_enabled:
                st.warning(f"⚠️ Arquivo grande ({size_mb:.1f} MB). A aba 'Visual' foi desabilitada.")
            st.session_state.pdf_doc_bytes_original = f.getvalue()
            st.session_state.pdf_name = f.name
            bms, pages, err = get_pdf_metadata(st.session_state.pdf_doc_bytes_original, f.name)
            if err:
                st.error(err); st.session_state.is_single_pdf_mode = False
            else:
                st.session_state.bookmarks_data = bms
                st.session_state.found_legal_pieces = find_legal_sections(bms)
                st.info(f"PDF '{f.name}' ({pages} páginas) carregado. Use as abas abaixo.")
        else:
            st.session_state.is_single_pdf_mode = False
            st.session_state.files_to_merge = uploaded_files
            st.info(f"{len(uploaded_files)} arquivos carregados. Vá para a aba 'Mesclar'.")
        st.rerun()

tabs = []
if st.session_state.get('is_single_pdf_mode', False):
    tabs.append("Peças Jurídicas")
    if st.session_state.get('visual_tab_enabled', False):
        tabs.append("Visual")
    tabs += ["Remover","Extrair","Dividir","Otimizar"]
tabs.append("Mesclar")
tab_objs = st.tabs(tabs)
tab_map = {name: tab for name, tab in zip(tabs, tab_objs)}

doc_cached = None
if st.session_state.get('is_single_pdf_mode', False):
    doc_cached = get_pdf_document(st.session_state.pdf_doc_bytes_original)
    if not doc_cached:
        st.error("PDF inválido/corrompido."); st.stop()
    base_name = os.path.splitext(st.session_state.pdf_name)[0]

# ---------- Mesclar ----------
if "Mesclar" in tab_map:
    with tab_map["Mesclar"]:
        st.header("🔗 Mesclar Múltiplos PDFs")
        files_to_merge = st.session_state.get('files_to_merge', [])
        if not files_to_merge:
            st.info("Para mesclar, carregue 2+ arquivos no upload acima.")
            if st.session_state.get('is_single_pdf_mode'): st.warning("Você está no modo de arquivo único.")
        else:
            def move_file(i, delta):
                fs = st.session_state.files_to_merge
                fs[i+delta], fs[i] = fs[i], fs[i+delta]
            for i,f in enumerate(files_to_merge):
                c_up,c_down,c_lbl = st.columns([0.08,0.08,0.84])
                if i>0: c_up.button("⬆️", key=f"up_{i}", on_click=move_file, args=(i,-1))
                if i < len(files_to_merge)-1: c_down.button("⬇️", key=f"down_{i}", on_click=move_file, args=(i,1))
                c_lbl.write(f"**{i+1}.** {f.name} ({round(f.size/1_048_576,2)} MB)")
            st.divider()
            c1,c2 = st.columns(2)
            optimize = c1.checkbox("Otimizar PDF final", True)
            pwd = c2.text_input("Senha (opcional)", type="password", key="pass_merge")
            if st.button("Executar Mesclagem", type="primary"):
                try:
                    with st.spinner("Mesclando..."):
                        merged = fitz.open()
                        for f in st.session_state.files_to_merge:
                            with fitz.open(stream=f.getvalue(), filetype="pdf") as src:
                                merged.insert_pdf(src)
                        generate_download_button(
                            merged, "documento_mesclado.pdf", "Baixar PDF Mesclado",
                            {"deflate_images": optimize, "deflate_fonts": optimize}, pwd
                        )
                except Exception as e:
                    st.error(f"Erro na mesclagem: {e}")

# ---------- Peças Jurídicas + Marcadores (todos) ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached:
    if "Peças Jurídicas" in tab_map:
        with tab_map["Peças Jurídicas"]:
            st.header("⚖️ Peças Jurídicas (por marcadores)")
            pcs = st.session_state.found_legal_pieces
            if not pcs:
                st.warning("Nenhuma peça reconhecida pelos marcadores.")
                st.info("Use 'Extrair' ou 'Visual' para selecionar páginas.")
            else:
                c1,c2,c3 = st.columns(3)
                if c1.button("Selecionar todas"):   [st.session_state.__setitem__(f"legal_piece_{p['unique_id']}", True) for p in pcs]
                if c2.button("Limpar seleção"):      [st.session_state.__setitem__(f"legal_piece_{p['unique_id']}", False) for p in pcs]
                if c3.button("Pré-seleção"):         [st.session_state.__setitem__(f"legal_piece_{p['unique_id']}", p['preselect']) for p in pcs]
                with st.container(height=320):
                    for p in pcs:
                        k = f"legal_piece_{p['unique_id']}"
                        if k not in st.session_state: st.session_state[k] = p['preselect']
                        st.checkbox(f"**{p['category']}**: {p['title']} (págs. {p['start_page_0_idx']+1}-{p['end_page_0_idx']+1})", key=k)
                st.divider()
                c1,c2 = st.columns(2)
                opt = c1.checkbox("Otimizar PDF", True, key="opt_legal")
                pwd = c2.text_input("Senha (opcional)", type="password", key="pass_legal")
                cz1,cz2 = st.columns(2)
                per_piece_zip = cz1.checkbox("Salvar cada peça separada (ZIP)", False)
                clean = cz2.checkbox("Remover metadados/anotações", False)
                if st.button("Extrair Peças Selecionadas", type="primary"):
                    ranges = [(p['start_page_0_idx'], p['end_page_0_idx'], p['title'])
                              for p in pcs if st.session_state.get(f"legal_piece_{p['unique_id']}", False)]
                    if not ranges: st.warning("Nenhuma peça selecionada.")
                    else:
                        try:
                            with st.spinner("Gerando saída..."):
                                if per_piece_zip:
                                    zb = io.BytesIO()
                                    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                                        for idx,(s,e,title) in enumerate(ranges,1):
                                            part = fitz.open(); insert_pages(part, doc_cached, list(range(s,e+1)))
                                            fd = fitz.open(stream=part.tobytes(), filetype="pdf")
                                            if clean:
                                                try: fd.set_metadata({})
                                                except: pass
                                                try:
                                                    for pg in fd:
                                                        ann = pg.first_annot
                                                        while ann:
                                                            nxt = ann.next
                                                            pg.delete_annot(ann); ann = nxt
                                                except: pass
                                            save_opts = dict(garbage=4, deflate=True, clean=True,
                                                             deflate_images=opt, deflate_fonts=opt)
                                            if pwd:
                                                save_opts.update({"encryption": ENCRYPT_AES_256, "user_pw": pwd, "owner_pw": pwd,
                                                                  "permissions": PERM_PRINT|PERM_COPY|PERM_ANNOTATE})
                                            outname = f"{base_name}_{idx:02d}_{safe_slug(title)}.pdf"
                                            zf.writestr(outname, fd.tobytes(**save_opts)); fd.close(); part.close()
                                    st.download_button("⬇️ Baixar ZIP das Peças", zb.getvalue(), f"{base_name}_pecas.zip", "application/zip")
                                else:
                                    new = fitz.open()
                                    pages = []
                                    for s,e,_ in ranges: pages += list(range(s,e+1))
                                    insert_pages(new, doc_cached, sorted(pages))
                                    generate_download_button(new, f"{base_name}_pecas.pdf", "Baixar Peças", 
                                                             {"deflate_images": opt, "deflate_fonts": opt},
                                                             pwd, remove_metadata=clean, remove_annotations=clean)
                        except Exception as e:
                            st.error(f"Erro ao extrair peças: {e}")

            st.subheader("📑 Exportar por Marcadores (todos)")
            cb1,cb2 = st.columns(2)
            level = cb1.number_input("Nível (1 = topo)", 1, 10, 1, 1, key="bm_any_level")
            txt = cb2.text_input("Filtrar por texto (opcional)", key="bm_any_text")
            selectable = [bm for bm in st.session_state.bookmarks_data
                          if bm.get("level",1)==level and (not txt or txt.lower() in bm["title"].lower())]
            if not selectable:
                st.info("Nenhum marcador encontrado para esses critérios.")
            else:
                for bm in selectable:
                    key = f"marker_piece_{bm['id']}"
                    if key not in st.session_state: st.session_state[key] = False
                with st.container(height=220):
                    for bm in selectable:
                        st.checkbox(f"{bm['title']} (págs. {bm['start_page_0_idx']+1}-{bm['end_page_0_idx']+1})", key=f"marker_piece_{bm['id']}")
                st.divider()
                cx1,cx2 = st.columns(2)
                per_marker_zip = cx1.checkbox("ZIP (um PDF por marcador)", True, key="zip_any_bm")
                opt_any = cx2.checkbox("Otimizar", True, key="opt_any_bm")
                cx3,cx4 = st.columns(2)
                pwd_any = cx3.text_input("Senha (opcional)", type="password", key="pass_any_bm")
                clean_any = cx4.checkbox("Remover metadados/anotações", False, key="clean_any_bm")
                if st.button("Exportar por Marcadores Selecionados", type="primary"):
                    chosen = [bm for bm in selectable if st.session_state.get(f"marker_piece_{bm['id']}", False)]
                    if not chosen: st.warning("Nenhum marcador selecionado.")
                    else:
                        try:
                            with st.spinner("Exportando marcadores..."):
                                if per_marker_zip:
                                    zb = io.BytesIO()
                                    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                                        for idx,bm in enumerate(chosen,1):
                                            part = fitz.open()
                                            insert_pages(part, doc_cached, list(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1)))
                                            fd = fitz.open(stream=part.tobytes(), filetype="pdf")
                                            if clean_any:
                                                try: fd.set_metadata({})
                                                except: pass
                                                try:
                                                    for pg in fd:
                                                        ann = pg.first_annot
                                                        while ann:
                                                            nxt = ann.next
                                                            pg.delete_annot(ann); ann = nxt
                                                except: pass
                                            save_opts = dict(garbage=4, deflate=True, clean=True,
                                                             deflate_images=opt_any, deflate_fonts=opt_any)
                                            if pwd_any:
                                                save_opts.update({"encryption": ENCRYPT_AES_256, "user_pw": pwd_any, "owner_pw": pwd_any,
                                                                  "permissions": PERM_PRINT|PERM_COPY|PERM_ANNOTATE})
                                            outname = f"{base_name}_{idx:02d}_p{bm['start_page_0_idx']+1:03d}_{safe_slug(bm['title'])}.pdf"
                                            zf.writestr(outname, fd.tobytes(**save_opts)); fd.close(); part.close()
                                    st.download_button("⬇️ Baixar ZIP (Marcadores)", zb.getvalue(), f"{base_name}_marcadores.zip", "application/zip")
                                else:
                                    new = fitz.open()
                                    for bm in chosen:
                                        insert_pages(new, doc_cached, list(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1)))
                                    generate_download_button(new, f"{base_name}_marcadores.pdf", "Baixar PDF (Marcadores)",
                                                             {"deflate_images": opt_any, "deflate_fonts": opt_any},
                                                             pwd_any, remove_metadata=clean_any, remove_annotations=clean_any)
                        except Exception as e:
                            st.error(f"Erro ao exportar por marcadores: {e}")

# ---------- Visual (miniaturas + reordenação) ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached and "Visual" in tab_map:
    with tab_map["Visual"]:
        st.header("🖼️ Visual — Seleção e Ordem")
        st.session_state.page_previews = build_previews(st.session_state.pdf_doc_bytes_original)
        st.sidebar.divider(); st.sidebar.subheader("Controles Visuais")
        n_cols = st.sidebar.slider("Colunas", 2, 10, 5, key="visual_cols")

        cols = st.columns(n_cols)
        for i, img_bytes in enumerate(st.session_state.page_previews):
            with cols[i % n_cols]:
                st.image(img_bytes, use_column_width=True, caption=f"Pág. {i+1}")
                cur = st.session_state.visual_page_selection.get(i, False)
                st.session_state.visual_page_selection[i] = st.checkbox("Selecionar", key=f"select_page_preview_{i}", value=cur)

        sel = [i for i,v in st.session_state.visual_page_selection.items() if v]
        st.sidebar.info(f"**{len(sel)}** de {doc_cached.page_count} páginas selecionadas.")
        a,b = st.sidebar.columns(2)
        def _all_on():  [st.session_state.visual_page_selection.__setitem__(i, True) for i in range(doc_cached.page_count)]
        def _all_off(): st.session_state.visual_page_selection.clear(); st.session_state.visual_custom_order.clear()
        a.button("Selecionar Todas", on_click=_all_on); b.button("Limpar", on_click=_all_off)

        st.divider()
        st.subheader("🧭 Ordem personalizada das selecionadas")
        order = st.session_state.get('visual_custom_order', [])
        sel_set = set(sel)
        for idx in sorted(sel):
            if idx not in order: order.append(idx)
        order = [i for i in order if i in sel_set]
        st.session_state.visual_custom_order = order

        def move_pos(pos, delta):
            lst = st.session_state.visual_custom_order
            np = pos + delta
            if 0 <= np < len(lst): lst[np], lst[pos] = lst[pos], lst[np]

        def remove_from_order(page_idx):
            st.session_state.visual_custom_order = [i for i in st.session_state.visual_custom_order if i != page_idx]
            st.session_state.visual_page_selection.pop(page_idx, None)

        if not order:
            st.info("Selecione páginas nas miniaturas acima para montar a ordem.")
        else:
            with st.container(height=260):
                for pos, p in enumerate(order):
                    cu, cd, cl, cr = st.columns([0.08,0.08,0.64,0.2])
                    if pos>0: cu.button("⬆️", key=f"reord_up_{p}_{pos}", on_click=move_pos, args=(pos,-1))
                    if pos<len(order)-1: cd.button("⬇️", key=f"reord_down_{p}_{pos}", on_click=move_pos, args=(pos,1))
                    cl.markdown(f"**{pos+1}.** Página {p+1}")
                    cr.button("Remover", key=f"reord_rm_{p}_{pos}", on_click=remove_from_order, args=(p,))

            c1,c2,c3 = st.columns(3)
            pwd_v = c1.text_input("Senha (opcional)", type="password", key="pass_visual")
            opt_v = c2.checkbox("Otimizar PDF", True, key="opt_visual")
            if c3.button("Limpar ordem"): st.session_state.visual_custom_order = []

            d1,d2 = st.columns(2)
            if d1.button("🗑️ Excluir Selecionadas", disabled=not sel):
                if len(sel) >= doc_cached.page_count:
                    st.error("Não é possível excluir todas as páginas.")
                else:
                    try:
                        with st.spinner("Excluindo..."):
                            new = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                            new.delete_pages(sorted(sel))
                            generate_download_button(new, f"{base_name}_excluido.pdf", "Baixar PDF Modificado", password=pwd_v)
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")

            if d2.button("✨ Extrair Selecionadas (ordem)", disabled=not order):
                try:
                    with st.spinner("Extraindo na ordem..."):
                        new = fitz.open(); insert_pages(new, doc_cached, order)
                        generate_download_button(new, f"{base_name}_extraido_visual_ordem.pdf", "Baixar PDF (Selecionadas em Ordem)",
                                                 {"deflate_images": opt_v, "deflate_fonts": opt_v}, pwd_v)
                except Exception as e:
                    st.error(f"Erro ao extrair: {e}")

            def full_reordered():
                chosen = order; all_idx = list(range(doc_cached.page_count))
                rest = [i for i in all_idx if i not in chosen]
                return chosen + rest

            if st.button("📑 Baixar PDF reordenado (todas as páginas)", disabled=not order):
                try:
                    with st.spinner("Reordenando documento..."):
                        new = fitz.open(); insert_pages(new, doc_cached, full_reordered())
                        generate_download_button(new, f"{base_name}_reordenado.pdf", "Baixar PDF Reordenado",
                                                 {"deflate_images": opt_v, "deflate_fonts": opt_v}, pwd_v)
                except Exception as e:
                    st.error(f"Erro ao reordenar: {e}")

# ---------- Remover ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached and "Remover" in tab_map:
    with tab_map["Remover"]:
        st.header("🗑️ Remover por Número ou Marcador")
        to_del = set()
        st.subheader("Remover por Marcador")
        f1 = st.text_input("Filtrar marcadores", key="del_bm_filter")
        with st.container(height=200):
            for bm in st.session_state.bookmarks_data:
                if not f1 or f1.lower() in bm['display_text'].lower():
                    if st.checkbox(bm['display_text'], key=f"del_{bm['id']}"):
                        to_del.update(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1))
        st.subheader("Remover por Número")
        nums = st.text_input("Ex.: 1, 3-5, 10", key="del_nums")
        to_del.update(parse_page_input(nums, doc_cached.page_count))
        st.divider()
        c1,c2 = st.columns(2)
        opt = c1.checkbox("Otimizar PDF", True, key="opt_rem")
        pwd = c2.text_input("Senha (opcional)", type="password", key="pass_rem")
        if st.button("Executar Remoção", type="primary", disabled=not to_del):
            if len(to_del)>=doc_cached.page_count: st.error("Não é possível remover todas as páginas.")
            else:
                try:
                    with st.spinner("Removendo..."):
                        new = fitz.open(stream=st.session_state.pdf_doc_bytes_original, filetype="pdf")
                        new.delete_pages(sorted(list(to_del)))
                        generate_download_button(new, f"{base_name}_removido.pdf", "Baixar PDF Modificado",
                                                 {"deflate_images": opt, "deflate_fonts": opt}, pwd)
                except Exception as e:
                    st.error(f"Erro ao remover: {e}")

# ---------- Extrair ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached and "Extrair" in tab_map:
    with tab_map["Extrair"]:
        st.header("✨ Extrair por Número ou Marcador")
        to_ext = set()
        st.subheader("Extrair por Marcador")
        f2 = st.text_input("Filtrar marcadores", key="ext_bm_filter")
        with st.container(height=200):
            for bm in st.session_state.bookmarks_data:
                if not f2 or f2.lower() in bm['display_text'].lower():
                    if st.checkbox(bm['display_text'], key=f"ext_{bm['id']}"):
                        to_ext.update(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1))
        st.subheader("Extrair por Número")
        nums = st.text_input("Ex.: 1, 3-5, 10", key="ext_nums")
        to_ext.update(parse_page_input(nums, doc_cached.page_count))
        st.divider()
        c1,c2 = st.columns(2)
        opt = c1.checkbox("Otimizar PDF", True, key="opt_ext")
        pwd = c2.text_input("Senha (opcional)", type="password", key="pass_ext")
        if st.button("Executar Extração", type="primary", disabled=not to_ext):
            try:
                with st.spinner("Extraindo..."):
                    new = fitz.open(); insert_pages(new, doc_cached, sorted(list(to_ext)))
                    generate_download_button(new, f"{base_name}_extraido.pdf", "Baixar PDF Extraído",
                                             {"deflate_images": opt, "deflate_fonts": opt}, pwd)
            except Exception as e:
                st.error(f"Erro ao extrair: {e}")

# ---------- Dividir ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached and "Dividir" in tab_map:
    with tab_map["Dividir"]:
        st.header("🔪 Dividir PDF")
        mode = st.radio("Método", ("A cada N páginas","Por tamanho (MB)","Por marcadores"), horizontal=True)
        opt = st.checkbox("Otimizar partes", True, key="opt_split")

        if mode=="A cada N páginas":
            n = st.number_input("N páginas por parte", 1, max(1,doc_cached.page_count), 10)
            if st.button("Dividir por Número", type="primary"):
                try:
                    with st.spinner("Dividindo..."):
                        parts = []
                        for i in range(0, doc_cached.page_count, n):
                            part = fitz.open()
                            rng = list(range(i, min(i+n, doc_cached.page_count)))
                            insert_pages(part, doc_cached, rng)
                            parts.append((f"{base_name}_parte_{i//n+1}.pdf",
                                          part.tobytes(garbage=3, deflate=True, clean=True,
                                                       deflate_images=opt, deflate_fonts=opt)))
                            part.close()
                        zb = io.BytesIO()
                        with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for name,data in parts: zf.writestr(name, data)
                        st.download_button("⬇️ Baixar ZIP", zb.getvalue(), f"{base_name}_partes.zip", "application/zip")
                except Exception as e:
                    st.error(f"Erro ao dividir: {e}")

        elif mode=="Por tamanho (MB)":
            max_mb = st.number_input("Tamanho por parte (MB)", .5, 500.0, 5.0, .1)
            warn_once = False
            if st.button("Dividir por Tamanho", type="primary"):
                try:
                    with st.spinner("Dividindo por tamanho..."):
                        parts = []; max_bytes = int(max_mb*1024*1024)
                        cur = fitz.open()
                        for p in range(doc_cached.page_count):
                            cur.insert_pdf(doc_cached, from_page=p, to_page=p)
                            tmp = cur.tobytes(garbage=1, deflate=True)
                            if len(tmp) > max_bytes:
                                if cur.page_count > 1:
                                    final = fitz.open()
                                    final.insert_pdf(cur, from_page=0, to_page=cur.page_count-2)
                                    parts.append((f"{base_name}_parte_{len(parts)+1}.pdf",
                                                  final.tobytes(garbage=3, deflate=True, clean=True,
                                                                deflate_images=opt, deflate_fonts=opt)))
                                    final.close()
                                    last = fitz.open()
                                    last.insert_pdf(cur, from_page=cur.page_count-1, to_page=cur.page_count-1)
                                    cur.close(); cur = last
                                else:
                                    if not warn_once:
                                        st.warning("Uma página isolada excede o limite e será salva sozinha.")
                                        warn_once = True
                                    parts.append((f"{base_name}_parte_{len(parts)+1}.pdf",
                                                  cur.tobytes(garbage=3, deflate=True, clean=True,
                                                              deflate_images=opt, deflate_fonts=opt)))
                                    cur.close(); cur = fitz.open()
                        if cur.page_count>0:
                            parts.append((f"{base_name}_parte_{len(parts)+1}.pdf",
                                          cur.tobytes(garbage=3, deflate=True, clean=True,
                                                      deflate_images=opt, deflate_fonts=opt)))
                        cur.close()
                        zb = io.BytesIO()
                        with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for name,data in parts: zf.writestr(name, data)
                        st.download_button("⬇️ Baixar ZIP", zb.getvalue(), f"{base_name}_partes_por_tamanho.zip", "application/zip")
                except Exception as e:
                    st.error(f"Erro ao dividir: {e}")

        else:  # Por marcadores
            st.write("Cria um arquivo por marcador (nível selecionado).")
            level = st.number_input("Nível do marcador", 1, 10, 1, 1)
            filt = st.text_input("Filtrar por texto (opcional)")
            if st.button("Dividir por Marcadores", type="primary"):
                try:
                    with st.spinner("Dividindo por marcadores..."):
                        parts = []
                        for bm in st.session_state.bookmarks_data:
                            if bm.get("level",1)!=level: continue
                            if filt and filt.lower() not in bm["title"].lower(): continue
                            part = fitz.open()
                            insert_pages(part, doc_cached, list(range(bm['start_page_0_idx'], bm['end_page_0_idx']+1)))
                            parts.append((f"{base_name}_{safe_slug(bm['title'])}.pdf",
                                          part.tobytes(garbage=3, deflate=True, clean=True,
                                                       deflate_images=opt, deflate_fonts=opt)))
                            part.close()
                        if not parts:
                            st.warning("Nenhum marcador encontrado.")
                        else:
                            zb = io.BytesIO()
                            with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for name,data in parts: zf.writestr(name, data)
                            st.download_button("⬇️ Baixar ZIP", zb.getvalue(), f"{base_name}_por_marcadores.zip", "application/zip")

# ---------- Otimizar ----------
if st.session_state.get('is_single_pdf_mode') and doc_cached and "Otimizar" in tab_map:
    with tab_map["Otimizar"]:
        st.header("🚀 Otimizar PDF")

        # Seleção de perfil de otimização
        profile = st.selectbox("Perfil", ("Leve", "Recomendada", "Máxima"), index=1)

        # Senha opcional
        pwd = st.text_input("Senha (opcional)", type="password", key="pass_opt")

        # Opções adicionais
        c1, c2 = st.columns(2)
        rm_meta = c1.checkbox("Remover metadados", True)
        rm_ann = c2.checkbox("Remover anotações", False)

        # Botão de ação
        if st.button("Otimizar Agora", type="primary"):
            try:
                with st.spinner("Otimizando..."):
                    # Configurações de otimização conforme perfil
                    opt = {}
                    if profile == "Leve":
                        opt.update(garbage=2, deflate=True)
                    elif profile == "Recomendada":
                        opt.update(garbage=4, deflate=True,
                                   deflate_images=True, deflate_fonts=True)
                    else:  # Máxima
                        opt.update(garbage=4, deflate=True,
                                   deflate_images=True, deflate_fonts=True,
                                   linear=True, clean=True)

                    # Abre documento original da sessão
                    doc = fitz.open(
                        stream=st.session_state.pdf_doc_bytes_original,
                        filetype="pdf"
                    )

                    # Gera botão de download
                    generate_download_button(
                        doc,
                        f"{base_name}_otimizado.pdf",
                        "Baixar PDF Otimizado",
                        opt,
                        pwd,
                        remove_metadata=rm_meta,
                        remove_annotations=rm_ann
                    )

            except Exception as e:
                st.error(f"Erro ao otimizar: {e}")

