import streamlit as st
from core.pdf_ops import merge_pdfs
from ui.components import render_download_button

def render(files_to_merge: list):
    st.header("🔗 Mesclar Múltiplos PDFs")
    
    if not files_to_merge:
        st.info("Para mesclar, carregue 2+ arquivos no upload acima.")
        return

    # Reordenação
    def move_file(i, delta):
        fs = st.session_state.files_to_merge
        if 0 <= i + delta < len(fs):
            fs[i+delta], fs[i] = fs[i], fs[i+delta]

    for i, f in enumerate(files_to_merge):
        c_up, c_down, c_lbl = st.columns([0.08, 0.08, 0.84])
        if i > 0:
            c_up.button("⬆️", key=f"up_{i}", on_click=move_file, args=(i, -1))
        if i < len(files_to_merge) - 1:
            c_down.button("⬇️", key=f"down_{i}", on_click=move_file, args=(i, 1))
        
        size_mb = f.size / (1024 * 1024) if hasattr(f, 'size') else 0
        c_lbl.write(f"**{i+1}.** {f.name} ({round(size_mb, 2)} MB)")

    st.divider()
    
    # Opções
    c1, c2 = st.columns(2)
    optimize = c1.checkbox("Otimizar PDF final", True, key="merge_opt")
    pwd = c2.text_input("Senha (opcional)", type="password", key="merge_pwd")

    if st.button("Executar Mesclagem", type="primary"):
        if len(files_to_merge) < 2:
            st.warning("Selecione pelo menos 2 arquivos.")
            return

        try:
            with st.spinner("Mesclando..."):
                # merge_pdfs espera lista de streams ou bytes
                # st.uploaded_files já são compatíveis pois têm .getvalue()
                # mas merge_pdfs em pdf_ops foi feita para lidar com isso.
                
                merged_bytes = merge_pdfs(files_to_merge, optimize=optimize, password=pwd)
                
                render_download_button(
                    merged_bytes, 
                    "documento_mesclado.pdf", 
                    "Baixar PDF Mesclado"
                )
        except Exception as e:
            st.error(f"Erro na mesclagem: {e}")
