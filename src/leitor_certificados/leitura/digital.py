"""Lê um PDF digital: o texto já está dentro do arquivo, letra por letra, com a posição.

O PDF não guarda "palavras" — guarda letras soltas, cada uma com o seu lugar na folha. Aqui
juntamos as letras vizinhas em palavras. Uma palavra termina quando:
- aparece um espaço ou uma quebra de linha;
- a próxima letra está em outra linha;
- a próxima letra está longe (colunas de uma tabela, que às vezes não têm espaço entre elas).
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .palavra import Pagina, Palavra

# Abaixo disso, a página é considerada "sem texto" (escaneada): alguns scanners gravam
# meia dúzia de letras invisíveis.
MINIMO_DE_LETRAS = 20


def _fechar(letras: list[tuple[str, tuple[float, float, float, float]]], largura: float,
            altura: float) -> Palavra:
    esq = min(c[0] for _, c in letras)
    base = min(c[1] for _, c in letras)
    dir_ = max(c[2] for _, c in letras)
    topo = max(c[3] for _, c in letras)
    # O PDF mede de baixo para cima; a nossa caixa mede de cima para baixo.
    caixa = (
        round(esq / largura, 4), round((altura - topo) / altura, 4),
        round(dir_ / largura, 4), round((altura - base) / altura, 4),
    )
    return Palavra("".join(letra for letra, _ in letras), caixa)


def ler_pagina_digital(pagina: pdfium.PdfPage) -> Pagina:
    largura, altura = pagina.get_size()
    texto = pagina.get_textpage()
    try:
        palavras: list[Palavra] = []
        atual: list[tuple[str, tuple[float, float, float, float]]] = []
        for i in range(texto.count_chars()):
            letra = chr(pdfium_c.FPDFText_GetUnicode(texto.raw, i))
            if letra.isspace() or letra == "\x00":
                if atual:
                    palavras.append(_fechar(atual, largura, altura))
                    atual = []
                continue
            caixa = texto.get_charbox(i, loose=True)  # esquerda, base, direita, topo (pontos)
            if atual:
                anterior = atual[-1][1]
                alt_letra = max(anterior[3] - anterior[1], 1.0)
                outra_linha = abs(caixa[1] - anterior[1]) > 0.5 * alt_letra
                longe = caixa[0] - anterior[2] > 0.6 * alt_letra or caixa[0] < anterior[0]
                if outra_linha or longe:
                    palavras.append(_fechar(atual, largura, altura))
                    atual = []
            atual.append((letra, caixa))
        if atual:
            palavras.append(_fechar(atual, largura, altura))
    finally:
        texto.close()
    return Pagina("digital", palavras)


def tem_texto(pagina: pdfium.PdfPage) -> bool:
    """A página tem texto de verdade (digital) ou é só imagem (escaneada)?"""
    texto = pagina.get_textpage()
    try:
        return texto.count_chars() >= MINIMO_DE_LETRAS
    finally:
        texto.close()


def ler_digital(caminho: Path | str) -> list[Pagina]:
    """Lê todas as páginas de um PDF digital."""
    documento = pdfium.PdfDocument(str(caminho))
    try:
        return [ler_pagina_digital(documento[i]) for i in range(len(documento))]
    finally:
        documento.close()
