import streamlit as st
import fitz
from core.pdf_ops import remove_pages, extract_pages
from core.utils import insert_pages
from ui.components import render_download_button, build_previews
import os

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🖼️ Visual — Seleção e Ordem")
    
    # Gera previews (cached)
    st.session_state.page_previews = build_previews(pdf_bytes_original)
    
    st.sidebar.divider()
    st.sidebar.subheader("Controles Visuais")
    n_cols = st.sidebar.slider("Colunas", 2, 10, 5, key="visual_cols")

    if 'visual_page_selection' not in st.session_state:
        st.session_state.visual_page_selection = {}
    if 'visual_custom_order' not in st.session_state:
        st.session_state.visual_custom_order = []

    cols = st.columns(n_cols)
    for i, img_bytes in enumerate(st.session_state.page_previews):
        with cols[i % n_cols]:
            st.image(img_bytes, use_column_width=True, caption=f"Pág. {i+1}")
            cur = st.session_state.visual_page_selection.get(i, False)
            st.session_state.visual_page_selection[i] = st.checkbox("Selecionar", key=f"select_page_preview_{i}", value=cur)

    sel = [i for i, v in st.session_state.visual_page_selection.items() if v]
    st.sidebar.info(f"**{len(sel)}** de {doc_cached.page_count} páginas selecionadas.")
    
    a, b = st.sidebar.columns(2)
    def _all_on():  
        for i in range(doc_cached.page_count): st.session_state.visual_page_selection[i] = True
    def _all_off(): 
        st.session_state.visual_page_selection = {}
        st.session_state.visual_custom_order = []
        
    a.button("Selecionar Todas", on_click=_all_on)
    b.button("Limpar", on_click=_all_off)

    st.divider()
    st.subheader("🧭 Ordem personalizada das selecionadas")
    
    # Atualiza lista de ordem baseada na seleção atual
    order = st.session_state.visual_custom_order
    sel_set = set(sel)
    # Adiciona novos selecionados ao final
    for idx in sorted(sel):
        if idx not in order: order.append(idx)
    # Remove desmarcados
    order = [i for i in order if i in sel_set]
    st.session_state.visual_custom_order = order

    def move_pos(pos, delta):
        lst = st.session_state.visual_custom_order
        np = pos + delta
        if 0 <= np < len(lst): lst[np], lst[pos] = lst[pos], lst[np]

    def remove_from_order(page_idx):
        st.session_state.visual_custom_order = [i for i in st.session_state.visual_custom_order if i != page_idx]
        st.session_state.visual_page_selection[page_idx] = False
        # Precisa de rerun pois o checkbox state não atualiza sozinho sem rerun/callback

    if not order:
        st.info("Selecione páginas nas miniaturas acima para montar a ordem.")
    else:
        with st.container(height=260):
            for pos, p in enumerate(order):
                cu, cd, cl, cr = st.columns([0.08, 0.08, 0.64, 0.2])
                if pos > 0: 
                    cu.button("⬆️", key=f"reord_up_{p}_{pos}", on_click=move_pos, args=(pos, -1))
                if pos < len(order) - 1: 
                    cd.button("⬇️", key=f"reord_down_{p}_{pos}", on_click=move_pos, args=(pos, 1))
                
                cl.markdown(f"**{pos+1}.** Página {p+1}")
                # Callback para remover e atualizar state
                cr.button("Remover", key=f"reord_rm_{p}_{pos}", on_click=remove_from_order, args=(p,))

        c1, c2, c3 = st.columns(3)
        pwd_v = c1.text_input("Senha (opcional)", type="password", key="pass_visual")
        opt_v = c2.checkbox("Otimizar PDF", True, key="opt_visual")
        if c3.button("Limpar ordem"): st.session_state.visual_custom_order = []

        base_name = os.path.splitext(pdf_name)[0]
        d1, d2 = st.columns(2)
        
        # Ação Excluir Selecionadas
        if d1.button("🗑️ Excluir Selecionadas", disabled=not sel):
            if len(sel) >= doc_cached.page_count:
                st.error("Não é possível excluir todas as páginas.")
            else:
                try:
                    with st.spinner("Excluindo..."):
                        new_bytes = remove_pages(pdf_bytes_original, sorted(sel), optimize=opt_v, password=pwd_v)
                        render_download_button(new_bytes, f"{base_name}_excluido.pdf", "Baixar PDF Modificado")
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")

        # Ação Extrair Selecionadas (Ordem)
        if d2.button("✨ Extrair Selecionadas (ordem)", disabled=not order):
            try:
                with st.spinner("Extraindo na ordem..."):
                    # extract_pages usa insert_pages que aceita lista ordenada
                    # Mas vamos usar fitz direto para garantir ordem exata customizada
                    # ou podemos passar order para extract_pages se ela suportar.
                    # extract_pages em pdf_ops usa insert_pages, que respeita ordem da lista?
                    # fitz.insert_pdf inserts pages. 
                    
                    # Vamos fazer manual aqui para garantir
                    new_doc = fitz.open()
                    insert_pages(new_doc, doc_cached, order)
                    
                    save_opts = {"garbage": 4, "deflate": True, "clean": True}
                    if opt_v: save_opts.update({"deflate_images": True, "deflate_fonts": True})
                    
                    # Senha logic... (simplificado)
                    out = new_doc.tobytes(**save_opts)
                    new_doc.close()
                    
                    render_download_button(out, f"{base_name}_extraido_visual_ordem.pdf", "Baixar PDF (Visual)")
            except Exception as e:
                st.error(f"Erro ao extrair: {e}")

        # Ação Reordenar Tudo
        def full_reordered():
            chosen = order
            all_idx = list(range(doc_cached.page_count))
            rest = [i for i in all_idx if i not in chosen]
            return chosen + rest

        if st.button("📑 Baixar PDF reordenado (todas as páginas)", disabled=not order):
            try:
                with st.spinner("Reordenando documento..."):
                    pages = full_reordered()
                    new_doc = fitz.open()
                    insert_pages(new_doc, doc_cached, pages)
                    # apply optimizations same way
                    save_opts = {"garbage": 4, "deflate": True, "clean": True}
                    if opt_v: save_opts.update({"deflate_images": True, "deflate_fonts": True})
                    
                    out = new_doc.tobytes(**save_opts)
                    new_doc.close()
                    
                    render_download_button(out, f"{base_name}_reordenado.pdf", "Baixar PDF Reordenado")
            except Exception as e:
                st.error(f"Erro ao reordenar: {e}")
