"""Lê um PDF escaneado com OCR local (RapidOCR): a folha é só uma foto, sem texto dentro.

OCR ("reconhecimento óptico de caracteres") faz o trabalho em duas partes:
1. **detecção** — acha onde há texto na imagem (as linhas);
2. **reconhecimento** — lê as letras de cada linha e diz o quanto tem certeza (`confianca`).

Tudo roda neste computador: os modelos vêm dentro da biblioteca, nada é enviado para fora
(ADR 0001). Diferente do PDF digital, o OCR **pode errar** (trocar `0` por `O`, perder um
acento) — por isso cada palavra guarda a confiança, que a etapa 3 pode usar.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium

from .palavra import Pagina, Palavra

# Resolução em que a página vira imagem para o OCR. 200 dpi é o comum de scanner: abaixo disso
# as letras pequenas da tabela ficam ilegíveis; acima, só fica mais lento.
DPI_OCR = 200


@lru_cache(maxsize=1)
def _motor():
    """Carrega o RapidOCR uma vez só (demora alguns segundos) e reaproveita."""
    from rapidocr import RapidOCR  # importado aqui: quem só lê PDF digital não paga essa espera

    return RapidOCR(params={"Global.log_level": "error"})


# Duas pistas de que a folha pode ter entrado de cabeça para baixo no scanner:
# 1. a confiança média do OCR ficou abaixo disto;
# 2. o título "CERTIFICADO" aparece só na metade de baixo da folha.
# Com qualquer uma, o OCR tenta também a folha virada 180° e fica com a melhor leitura.
CONFIANCA_PARA_TESTAR_GIRO = 0.93


def _titulo_no_alto(palavras: list[Palavra]) -> int:
    """1 se "certificado" aparece na metade de cima, -1 se só na de baixo, 0 se não aparece."""
    # Só conta o título de verdade ("CERTIFICADO DE CALIBRAÇÃO"): o carimbo "ESTE CERTIFICADO FOI
    # ANALISADO", que também tem a palavra, enganava a regra numa folha invertida.
    ys = [
        p.centro[1] for i, p in enumerate(palavras[:-1])
        if p.texto.strip(" :.").lower() == "certificado"
        and palavras[i + 1].texto.strip(" :.").lower() == "de"
    ]
    if not ys:
        return 0
    return 1 if min(ys) < 0.5 else -1


def _ler_imagem(imagem) -> list[Palavra]:
    altura, largura = imagem.shape[:2]
    resultado = _motor()(imagem, return_word_box=True)
    palavras: list[Palavra] = []
    for linha in resultado.word_results or ():
        for texto, confianca, cantos in linha:
            texto = _limpar(texto)
            if not texto:
                continue
            xs = [x for x, _ in cantos]
            ys = [y for _, y in cantos]
            caixa = (
                round(max(min(xs), 0) / largura, 4), round(max(min(ys), 0) / altura, 4),
                round(min(max(xs), largura) / largura, 4),
                round(min(max(ys), altura) / altura, 4),
            )
            palavras.extend(_separar_rotulo(Palavra(texto, caixa, round(float(confianca), 4))))
    return palavras


def _pontuacao(palavras: list[Palavra]) -> tuple[float, float]:
    """(confiança média, soma das confianças) das palavras com 3 letras ou mais. A soma premia a
    orientação em que o OCR achou mais palavras de verdade; a média decide se vale testar o giro."""
    confiancas = [p.confianca for p in palavras if len(p.texto) >= 3]
    if not confiancas:
        return 0.0, 0.0
    return sum(confiancas) / len(confiancas), sum(confiancas)


def ler_pagina_ocr(pagina: pdfium.PdfPage) -> Pagina:
    import numpy as np

    imagem = np.array(pagina.render(scale=DPI_OCR / 72).to_pil().convert("RGB"))
    normal = _ler_imagem(imagem)
    media, soma = _pontuacao(normal)
    titulo = _titulo_no_alto(normal)
    if media >= CONFIANCA_PARA_TESTAR_GIRO and titulo >= 0:
        return Pagina("ocr", normal)
    virada = _ler_imagem(np.ascontiguousarray(imagem[::-1, ::-1]))
    melhor_virada = (_titulo_no_alto(virada), _pontuacao(virada)[1]) > (titulo, soma)
    return Pagina("ocr", virada, rotacao=180) if melhor_virada else Pagina("ocr", normal)


def _limpar(texto: str) -> str:
    """Acertos seguros, que não mudam o que está escrito: o OCR às vezes devolve o símbolo
    único "℃" no lugar de "°C" (ou os dois juntos, "°℃")."""
    return texto.strip().replace("℃", "°C").replace("°°", "°")


def _separar_rotulo(palavra: Palavra) -> list[Palavra]:
    """O OCR às vezes gruda o rótulo na resposta ("CERTIFICADO:QV050294"). Separa depois dos
    dois-pontos, dividindo a caixa na proporção do número de letras de cada parte."""
    antes, dois_pontos, depois = palavra.texto.partition(":")
    if not (dois_pontos and depois and len(antes) >= 2 and antes.isalpha()):
        return [palavra]
    esq, topo, dir_, base = palavra.caixa
    corte = round(esq + (dir_ - esq) * (len(antes) + 1) / len(palavra.texto), 4)
    return [
        Palavra(antes + ":", (esq, topo, corte, base), palavra.confianca),
        Palavra(depois, (corte, topo, dir_, base), palavra.confianca),
    ]


def ler_ocr(caminho: Path | str) -> list[Pagina]:
    """Lê todas as páginas de um PDF escaneado."""
    documento = pdfium.PdfDocument(str(caminho))
    try:
        return [ler_pagina_ocr(documento[i]) for i in range(len(documento))]
    finally:
        documento.close()
