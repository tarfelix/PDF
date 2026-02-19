import streamlit as st
import fitz
from core.pdf_ops import remove_pages, extract_pages, rotate_pages
from core.utils import insert_pages
from ui.components import render_download_button, build_previews
import os

def render(doc_cached: fitz.Document, pdf_bytes_original: bytes, pdf_name: str):
    st.header("🖼️ Visual — Seleção, Ordem e Rotação")
    
    # Init state de rotações
    if 'visual_rotations' not in st.session_state:
        st.session_state.visual_rotations = {} # {idx: angle}

    # Gera previews (cached, mas dependente das rotações agora)
    # Como st.cache_resource usa hash dos argumentos, passar o dict de rotação deve invalidar o cache qd mudar
    # Mas dicts nao sao hashable por padrao em python puro, porem streamlit lida com isso.
    # Vamos converter para tupla ordenada para garantir estabilidade do cache se necessario, 
    # mas o streamlit costuma lidar bem.
    
    st.session_state.page_previews = build_previews(
        pdf_bytes_original, 
        rotations=st.session_state.visual_rotations.copy()
    )
    
    st.sidebar.divider()
    st.sidebar.subheader("Controles Visuais")
    n_cols = st.sidebar.slider("Colunas", 2, 10, 5, key="visual_cols")

    if 'visual_page_selection' not in st.session_state:
        st.session_state.visual_page_selection = {}
    if 'visual_custom_order' not in st.session_state:
        st.session_state.visual_custom_order = []

    # Ações em lote na sidebar
    st.sidebar.caption("Rotação em lote (selecionadas)")
    c_rot_l, c_rot_r = st.sidebar.columns(2)
    selected_indices = [i for i, v in st.session_state.visual_page_selection.items() if v]
    
    def rotate_selected(angle_delta):
        for idx in selected_indices:
            cur = st.session_state.visual_rotations.get(idx, 0)
            st.session_state.visual_rotations[idx] = (cur + angle_delta) % 360
        # Limpa cache de previews se mudar rotação? O streamlit deve detectar mudança no arg
        # build_previews.clear() # Talvez necessario se o cache for persistente demais
        
    if c_rot_l.button("↺ Esq", disabled=not selected_indices): rotate_selected(-90)
    if c_rot_r.button("↻ Dir", disabled=not selected_indices): rotate_selected(90)


    cols = st.columns(n_cols)
    for i, img_bytes in enumerate(st.session_state.page_previews):
        with cols[i % n_cols]:
            st.image(img_bytes, use_column_width=True, caption=f"Pág. {i+1}")
            
            # Controles individuais de cada página
            c_chk, c_rot = st.columns([0.6, 0.4])
            
            cur = st.session_state.visual_page_selection.get(i, False)
            st.session_state.visual_page_selection[i] = c_chk.checkbox("Sel.", key=f"select_page_preview_{i}", value=cur)
            
            if c_rot.button("↻", key=f"rot_btn_{i}"):
                cur_rot = st.session_state.visual_rotations.get(i, 0)
                st.session_state.visual_rotations[i] = (cur_rot + 90) % 360
                st.rerun()

    sel = [i for i, v in st.session_state.visual_page_selection.items() if v]
    st.sidebar.info(f"**{len(sel)}** de {doc_cached.page_count} páginas selecionadas.")
    
    a, b = st.sidebar.columns(2)
    def _all_on():  
        for i in range(doc_cached.page_count): st.session_state.visual_page_selection[i] = True
    def _all_off(): 
        st.session_state.visual_page_selection = {}
        st.session_state.visual_custom_order = []
        st.session_state.visual_rotations = {} # Reset rotações tbm? Talvez nao.
        
    a.button("Selecionar Todas", on_click=_all_on)
    b.button("Limpar Seleção", on_click=_all_off)

    st.divider()
    
    # Se houver rotações, oferecer salvar só as rotações
    if st.session_state.visual_rotations:
        st.subheader("💾 Salvar Alterações de Rotação")
        valid_rot = {k:v for k,v in st.session_state.visual_rotations.items() if v != 0}
        if valid_rot:
            st.caption(f"{len(valid_rot)} páginas com rotação modificada.")
            if st.button("Salvar PDF com Rotações Aplicadas", type="secondary"):
                try:
                    with st.spinner("Aplicando rotações..."):
                        base_name = os.path.splitext(pdf_name)[0]
                        # Aplica rotação no PDF completo
                        new_bytes = rotate_pages(pdf_bytes_original, valid_rot, optimize=True)
                        render_download_button(new_bytes, f"{base_name}_rotacionado.pdf", "Baixar PDF Rotacionado")
                except Exception as e:
                    st.error(f"Erro ao rotacionar: {e}")
        st.divider()

    st.subheader("🧭 Ordem personalizada (Extração/Exclusão)")
    
    # Atualiza lista de ordem
    order = st.session_state.visual_custom_order
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
        st.session_state.visual_page_selection[page_idx] = False
        
    if order:
        with st.container(height=260):
            for pos, p in enumerate(order):
                cu, cd, cl, cr = st.columns([0.08, 0.08, 0.64, 0.2])
                if pos > 0: 
                    cu.button("⬆️", key=f"reord_up_{p}_{pos}", on_click=move_pos, args=(pos, -1))
                if pos < len(order) - 1: 
                    cd.button("⬇️", key=f"reord_down_{p}_{pos}", on_click=move_pos, args=(pos, 1))
                
                rot_txt = f" (↻ {st.session_state.visual_rotations[p]}°)" if st.session_state.visual_rotations.get(p) else ""
                cl.markdown(f"**{pos+1}.** Página {p+1}{rot_txt}")
                cr.button("Remover", key=f"reord_rm_{p}_{pos}", on_click=remove_from_order, args=(p,))

        c1, c2, c3 = st.columns(3)
        pwd_v = c1.text_input("Senha (opcional)", type="password", key="pass_visual")
        opt_v = c2.checkbox("Otimizar PDF", True, key="opt_visual")
        if c3.button("Limpar ordem"): st.session_state.visual_custom_order = []

        base_name = os.path.splitext(pdf_name)[0]
        d1, d2 = st.columns(2)
        
        # Ação Excluir
        if d1.button("🗑️ Excluir Selecionadas", disabled=not sel):
            if len(sel) >= doc_cached.page_count: st.error("Não é possível excluir tudo.")
            else:
                try:
                    with st.spinner("Processando..."):
                        # Para exclusão, idealmente rodar rotações primeiro? 
                        # pdf_ops.remove_pages remove do original.
                        # Se tiver rotação, melhor aplicar rotação em tudo e depois remover?
                        # Isso pode ser pesado.
                        # Melhor: processar uma copia temporaria se houver rotações.
                        
                        src_bytes = pdf_bytes_original
                        valid_rot = {k:v for k,v in st.session_state.visual_rotations.items() if v != 0}
                        if valid_rot:
                            src_bytes = rotate_pages(src_bytes, valid_rot, False)
                            
                        new_bytes = remove_pages(src_bytes, sorted(sel), optimize=opt_v, password=pwd_v)
                        render_download_button(new_bytes, f"{base_name}_excluido.pdf", "Baixar PDF Modificado")
                except Exception as e:
                    st.error(f"Erro: {e}")

        # Ação Extrair (Ordem)
        if d2.button("✨ Extrair Selecionadas (ordem)", disabled=not order):
            try:
                with st.spinner("Extraindo..."):
                    
                    # Se houver rotações, precisamos aplicar nas páginas extraídas
                    # Melhor estratégia: criar novo doc, inserir páginas na ordem, e rotacionar as novas páginas
                    
                    new_doc = fitz.open()
                    # insert_pages copia do original
                    # Precisamos copiar paginas uma a uma para aplicar rotação individual se insert_pages nao suportar
                    # fitz.Document.insert_pdf(src, from_page=x, to_page=x, rotate=angle) suporta rotação!
                    
                    src = fitz.open(stream=pdf_bytes_original, filetype="pdf")
                    for page_idx in order:
                        rot = st.session_state.visual_rotations.get(page_idx, 0)
                        # O angulo em insert_pdf é relativo? ou absoluto? Doc diz: rotate=-1 (default, copy source), ou 0, 90...
                        # Se passarmos rotate=rot, ele define a rotação no destino.
                        # Porém, se a pagina original ja tinha rotação (ex 90) e usuario nao mudou (0 visualmente), mantemos original (-1)
                        # Se usuario mudou visualmente e visual_rotations guarda O ESTADO FINAL DESEJADO ou o DELTA?
                        # O codigo acima faz (cur + 90) % 360, entao guarda ESTADO RELATIVO A 0 se assumirmos que a visualização inicial é 0.
                        # Na verdade build_previews renderiza como está no arquivo (GetPixmap). 
                        # Se page.set_rotation altera o objeto page, cuidado. O fitz doc é aberto a cada build_previews.
                        # Resumindo: `visual_rotations` guarda o angulo final absoluto que queremos setar.
                        
                        r = rot if page_idx in st.session_state.visual_rotations else -1
                        new_doc.insert_pdf(src, from_page=page_idx, to_page=page_idx, rotate=r)
                        
                    src.close()
                    
                    save_opts = {"garbage": 4, "deflate": True, "clean": True}
                    if opt_v: save_opts.update({"deflate_images": True, "deflate_fonts": True})
                     # Senha logic... (simplificado, ideal usar helper do core se possivel ou replicar)
                    if pwd_v:
                         from config import ENCRYPT_AES_256, PERM_PRINT, PERM_COPY, PERM_ANNOTATE
                         save_opts.update({
                            "encryption": ENCRYPT_AES_256, "user_pw": pwd_v, "owner_pw": pwd_v,
                            "permissions": PERM_PRINT | PERM_COPY | PERM_ANNOTATE
                         })

                    out = new_doc.tobytes(**save_opts)
                    new_doc.close()
                    
                    render_download_button(out, f"{base_name}_extraido_ordem.pdf", "Baixar PDF")
            except Exception as e:
                st.error(f"Erro: {e}")
