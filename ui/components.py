import streamlit as st
import fitz
from ui.styles import inject_brand_css

@st.cache_resource(show_spinner="Gerando miniaturas...")
def build_previews(pdf_bytes: bytes, dpi=48, rotations: dict = None):
    """Gera imagens de preview para visualização, aplicando rotações se fornecidas."""
    if rotations is None: rotations = {}
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        previews = []
        for i, pg in enumerate(doc):
            if i in rotations:
                pg.set_rotation(rotations[i])
            previews.append(pg.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72)).tobytes("png"))
        return previews

@st.cache_data(max_entries=5, show_spinner="Lendo sumário...")
def get_pdf_metadata_cached(pdf_bytes: bytes, name="pdf"):
    """Wrapper com cache para extração de metadados."""
    from core.pdf_scanner import get_bookmark_ranges
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
            return get_bookmark_ranges(d), d.page_count, None
    except Exception as e:
        return [], 0, f"Erro ao ler {name}: {e}"

@st.cache_resource(show_spinner="Abrindo PDF...")
def get_pdf_document(pdf_bytes):
    """Retorna objeto Document do PyMuPDF (cached)."""
    if not pdf_bytes: return None
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Não foi possível abrir o PDF: {e}")
        return None

def brand_header(brand: dict, high_contrast: bool):
    """Exibe o cabeçalho personalizado."""
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

def render_download_button(data: bytes, filename: str, label: str):
    """Wrapper consistente para download buttons."""
    col1, _ = st.columns([0.4, 0.6]) # Ajuste de layout se necessário
    st.download_button(
        label=f"⬇️ {label}",
        data=data,
        file_name=filename,
        mime="application/pdf"
    )
    st.success(f"Arquivo pronto: {filename}")
