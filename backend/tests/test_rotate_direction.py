"""Issue #3 — rotação saindo ao contrário.

O botão do editor (RotateCw) gira 90° horário e a prévia usa CSS
`transform: rotate(+90deg)` (também horário). O PyMuPDF `set_rotation(90)` é
horário igual à prévia. Um bug em `rotate_pages` chamava `set_rotation(-angle)`,
invertendo o sentido: um pedido de +90 (direita) gerava /Rotate=270
(esquerda). Este teste fixa que o /Rotate resultante casa com o ângulo pedido
(sem negação) — falha contra `set_rotation(-angle)`, passa com `set_rotation(angle)`.
"""
from __future__ import annotations

import fitz
import pytest

from core.pdf_ops import rotate_pages


def _one_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=300)
    return doc.tobytes()


@pytest.mark.parametrize("angle", [90, 180, 270])
def test_rotacao_horaria_casa_com_previa(angle):
    """+angle (horário, igual à prévia CSS) -> /Rotate == angle, nunca invertido."""
    out = rotate_pages(_one_page_pdf(), {0: angle}, optimize=False)
    with fitz.open(stream=out, filetype="pdf") as res:
        assert res[0].rotation == angle


def test_pagina_sem_rotacao_nao_muda():
    out = rotate_pages(_one_page_pdf(), {0: 0}, optimize=False)
    with fitz.open(stream=out, filetype="pdf") as res:
        assert res[0].rotation == 0
