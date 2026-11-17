"""Carimbo digital de aprovação (etapa 11).

Substitui o carimbo de papel ("ESTE CERTIFICADO FOI ANALISADO CRITICAMENTE E CONSIDERADO:
( X ) APROVADO") por um desenho limpo, em alta definição, com RE, nome (VISTO) e data de quem
aprovou. O carimbo vai numa CÓPIA do PDF; o original nunca é alterado.

O lugar é escolhido sozinho (decisão do usuário, 2026-11-17): o maior espaço em branco da
página, de baixo para cima, onde o carimbo cabe sem cobrir nada escrito.
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 1400, 520  # pixels do desenho (alta definição)
TINTA = (20, 20, 20, 255)  # preto do carimbo
CANETA = (25, 55, 150, 255)  # azul do que a pessoa "escreve"
FONTES = Path("C:/Windows/Fonts")
LARGURA_NA_FOLHA = 0.34  # o carimbo ocupa 34 % da largura da página (igual ao de papel)


def _fonte(nomes: tuple[str, ...], tamanho: int) -> ImageFont.ImageFont:
    for nome in nomes:
        try:
            return ImageFont.truetype(str(FONTES / nome), tamanho)
        except OSError:
            try:
                return ImageFont.truetype(nome, tamanho)
            except OSError:
                continue
    return ImageFont.load_default(tamanho)


def desenhar(nome: str, re: str, data: str) -> Image.Image:
    """O carimbo, com o RE, o nome no VISTO e a data. Fundo branco: a marca d'água ou uma
    linha do certificado nunca aparecem por dentro (sempre limpo e fácil de ler)."""
    imagem = Image.new("RGBA", (LARGURA, ALTURA), (255, 255, 255, 255))
    d = ImageDraw.Draw(imagem)
    negrito = ("arialbd.ttf", "DejaVuSans-Bold.ttf")
    normal = ("arial.ttf", "DejaVuSans.ttf")
    d.rectangle((8, 8, LARGURA - 9, ALTURA - 9), outline=TINTA, width=10)
    titulo = _fonte(negrito, 62)
    d.text((LARGURA / 2, 85), "ESTE CERTIFICADO FOI ANALISADO", font=titulo, fill=TINTA,
           anchor="mm")
    d.text((LARGURA / 2, 165), "CRITICAMENTE E CONSIDERADO:", font=titulo, fill=TINTA,
           anchor="mm")
    opcao = _fonte(negrito, 58)
    d.text((60, 275), "( X ) APROVADO", font=opcao, fill=TINTA, anchor="lm")
    d.text((LARGURA - 60, 275), "(    ) REPROVADO", font=opcao, fill=TINTA, anchor="rm")
    y = 420
    rotulo = _fonte(negrito, 50)
    valor = _fonte(normal, 50)
    # o nome em letra de mão; se for comprido, a letra diminui para caber no espaço
    tamanho = 48
    assinatura = _fonte(("segoesc.ttf",) + normal, tamanho)
    while tamanho > 20 and d.textlength(nome, font=assinatura) > 520:
        tamanho -= 2
        assinatura = _fonte(("segoesc.ttf",) + normal, tamanho)
    d.text((40, y), "RE:", font=rotulo, fill=TINTA, anchor="ls")
    d.text((140, y), re, font=valor, fill=CANETA, anchor="ls")
    d.text((360, y), "VISTO:", font=rotulo, fill=TINTA, anchor="ls")
    d.text((545, y), nome, font=assinatura, fill=CANETA, anchor="ls")
    d.text((LARGURA - 40, y), data, font=valor, fill=CANETA, anchor="rs")
    for x0, x1 in ((135, 340), (540, 1080), (1090, LARGURA - 35)):
        d.line((x0, y + 14, x1, y + 14), fill=TINTA, width=3)
    return imagem


def lugar_livre(pagina: Image.Image, largura: float = LARGURA_NA_FOLHA) -> tuple[float, float]:
    """Onde o carimbo cabe sem cobrir nada: (esquerda, topo) em fração da página.

    Procura de baixo para cima (o carimbo de papel vai embaixo) e, em cada altura, da direita
    para a esquerda, o primeiro retângulo do tamanho do carimbo sem tinta. Sem lugar livre,
    fica no canto de baixo à direita, acima da margem.
    """
    import numpy as np

    cinza = np.asarray(pagina.convert("L"))
    # a página em blocos pequenos (1/200 da largura); cada
    # bloco guarda o pixel MAIS ESCURO dele, para uma linha fina não sumir ao diminuir.
    bloco = max(1, cinza.shape[1] // 200)
    alto, largo = cinza.shape[0] // bloco, cinza.shape[1] // bloco
    cinza = cinza[:alto * bloco, :largo * bloco]
    escuro = cinza.reshape(alto, bloco, largo, bloco).min(axis=(1, 3))
    lw, lh = largo, alto
    cw = round(lw * largura)
    ch = round(cw * ALTURA / LARGURA)
    margem = round(lw * 0.04)
    # tinta = mais escuro que a marca d'água clara dos laboratórios
    tinta = (escuro < 170).astype(int).tolist()
    # soma acumulada 2D: conta a tinta de um retângulo de uma vez
    soma = [[0] * (lw + 1) for _ in range(lh + 1)]
    for y in range(lh):
        linha = 0
        for x in range(lw):
            linha += tinta[y][x]
            soma[y + 1][x + 1] = soma[y][x + 1] + linha

    def tem_tinta(x: int, y: int) -> bool:
        x0, y0 = x - margem // 2, y - margem // 2
        x1, y1 = x + cw + margem // 2, y + ch + margem // 2
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(lw, x1), min(lh, y1)
        return soma[y1][x1] - soma[y0][x1] - soma[y1][x0] + soma[y0][x0] > 0

    # a metade de baixo da página primeiro, subindo
    for y in range(lh - ch - margem, lh // 2, -1):
        for x in range(lw - cw - margem, margem - 1, -1):
            if not tem_tinta(x, y):
                return x / lw, y / lh
    return (lw - cw - margem) / lw, (lh - ch - margem * 3) / lh


def sobrepor(origem: Path | str, destino: Path | str,
             camadas: list[tuple[Image.Image, float, float, float]], rotacao: int = 0) -> Path:
    """Grava em `destino` uma cópia do PDF com imagens por cima da 1ª página.

    Cada camada é (imagem, esquerda, topo, largura), em fração da página EM PÉ (como a tela a
    mostra); a altura sai da proporção da imagem. Com `rotacao=180` (folha escaneada de cabeça
    para baixo) a imagem e o lugar são virados, para cair no lugar certo do PDF original.
    """
    destino = Path(destino)
    documento = pdfium.PdfDocument(str(origem))
    try:
        pagina = documento[0]
        largura_pt, altura_pt = pagina.get_size()
        for figura, esquerda, topo, largura in camadas:
            w = largura_pt * largura
            h = w * figura.height / figura.width
            if rotacao == 180:
                figura = figura.rotate(180)
                esquerda = 1 - esquerda - largura
                topo = 1 - topo - h / altura_pt
            imagem = pdfium.PdfImage.new(documento)
            imagem.set_bitmap(pdfium.PdfBitmap.from_pil(figura))
            # no PDF o y cresce para cima: a base da imagem fica em altura − topo − h
            imagem.set_matrix(pdfium.PdfMatrix().scale(w, h).translate(
                esquerda * largura_pt, altura_pt - topo * altura_pt - h))
            pagina.insert_obj(imagem)
        pagina.gen_content()
        destino.parent.mkdir(parents=True, exist_ok=True)
        documento.save(str(destino))
    finally:
        documento.close()
    return destino


def carimbar_pdf(origem: Path | str, destino: Path | str, nome: str, re: str, data: str,
                 rotacao: int = 0) -> Path:
    """Grava em `destino` uma cópia do PDF com o carimbo na 1ª página, no espaço livre."""
    documento = pdfium.PdfDocument(str(origem))
    try:
        folha = documento[0].render(scale=1).to_pil()
    finally:
        documento.close()
    if rotacao == 180:
        folha = folha.rotate(180)
    esquerda, topo = lugar_livre(folha)
    return sobrepor(origem, destino, [(desenhar(nome, re, data), esquerda, topo,
                                       LARGURA_NA_FOLHA)], rotacao)
