import streamlit as st

def inject_brand_css(brand: dict, high_contrast: bool):
    """Injeta CSS customizado baseado na marca."""
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
