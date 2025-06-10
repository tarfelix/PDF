# ✂️ Editor e Divisor de PDF Completo (PT-BR)

Aplicativo **Streamlit** para manipulação avançada de PDFs em português:  
mesclar, dividir, extrair páginas, otimizar e identificar/recortar peças jurídicas com pré-seleção inteligente.

![screenshot](docs/screenshot.png)

---

## Funcionalidades

| Recurso | Descrição |
|---------|-----------|
| **Mesclar PDFs** | Arraste vários arquivos e gere um único PDF, com opção de otimizar o resultado. |
| **Extrair Peças Jurídicas** | Reconhece marcadores (PJe, e-SAJ etc.) e pré-seleciona sentenças, decisões, recursos, laudos e afins. |
| **Gerir Páginas Visualmente** | Miniaturas interativas para marcar páginas e **excluir** ou **extrair** com um clique. |
| **Remover / Extrair por Marcadores ou Números** | Selecione marcadores (TOC) ou digite intervalos como `1,3-5,8` para recortar. |
| **Dividir PDF** | • Por tamanho máximo (MB)  • A cada _N_ páginas  • Gera ZIP com todas as partes. |
| **Otimizar PDF** | Perfis *Leve*, *Recomendada* e *Máxima* (limpeza de lixo, deflate, compressão de imagens/fontes). |
| **Segurança integrada** | Impede excluir **todas** as páginas por engano;  mantém ordem cronológica na extração de peças. |

---

## Requisitos

| Pacote | Versão mínima |
|--------|---------------|
| Python | 3.9+ |
| [Streamlit](https://streamlit.io) | 1.33 |
| [PyMuPDF](https://pymupdf.readthedocs.io) (import `fitz`) | 1.23 |
| Pillow | 9.5 |
| Unidecode | 1.3 |

> Instale tudo com:

```bash
pip install -r requirements.txt
