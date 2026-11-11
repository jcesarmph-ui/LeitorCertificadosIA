"""Etapa 2 — ler o PDF: transforma a folha numa lista de palavras, cada uma com a sua posição.

- PDF digital: o texto já está no arquivo (`digital.py`);
- PDF escaneado: é só uma foto, precisa de OCR (`ocr.py`).

O resultado tem o mesmo formato nos dois casos (`Pagina` com `Palavra`s), para o machine learning
da etapa 3 não precisar saber de onde a palavra veio.
"""

from .palavra import Pagina, Palavra

__all__ = ["Pagina", "Palavra"]
