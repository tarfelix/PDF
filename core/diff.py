import fitz
import difflib
from typing import Tuple

def compare_pdfs(pdf1_bytes: bytes, pdf2_bytes: bytes) -> str:
    """
    Compara o texto de dois PDFs e retorna um HTML com as diferenças coloridas.
    """
    doc1 = fitz.open(stream=pdf1_bytes, filetype="pdf")
    doc2 = fitz.open(stream=pdf2_bytes, filetype="pdf")
    
    text1 = ""
    for page in doc1: text1 += page.get_text() + "\n"
        
    text2 = ""
    for page in doc2: text2 += page.get_text() + "\n"
    
    doc1.close()
    doc2.close()
    
    d = difflib.HtmlDiff(wrapcolumn=80)
    # make_file retorna uma string HTML completa
    html_diff = d.make_file(text1.splitlines(), text2.splitlines(), fromdesc="Original", todesc="Modificado", context=True, numlines=2)
    
    return html_diff
