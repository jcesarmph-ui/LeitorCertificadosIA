"""Porta de entrada da leitura: recebe qualquer PDF e escolhe o caminho, página por página.

- a página tem texto dentro → leitura direta (rápida e exata);
- a página é só imagem → OCR (mais lento, pode errar).

Um mesmo PDF pode misturar os dois (ex.: certificado digital com um anexo escaneado).
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from .digital import ler_pagina_digital, tem_texto
from .palavra import Pagina


def ler_pdf(caminho: Path | str) -> list[Pagina]:
    documento = pdfium.PdfDocument(str(caminho))
    try:
        paginas: list[Pagina] = []
        for i in range(len(documento)):
            pagina = documento[i]
            if tem_texto(pagina):
                paginas.append(ler_pagina_digital(pagina))
            else:
                from .ocr import ler_pagina_ocr  # só carrega o OCR se precisar

                paginas.append(ler_pagina_ocr(pagina))
        return paginas
    finally:
        documento.close()
