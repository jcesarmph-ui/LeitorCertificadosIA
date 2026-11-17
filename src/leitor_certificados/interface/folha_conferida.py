"""Os checks da conferência desenhados por cima do PDF (etapa 11).

O auditor que abrir o certificado registrado vê o mesmo que a tela principal mostrou depois da
análise: ✓ verde (ou ✗ vermelho / ! amarelo) em cada ponto conferido, em cada padrão (validade)
e em cada informação do instrumento comparada com o cadastro (código, tipo, fabricante…).

Desenhado com o Pillow numa imagem transparente do tamanho da página, sem depender da tela.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..conferencia.avaliacao import Resultado
from ..conferencia.cadastro import CAMPOS as CAMPOS_CADASTRO
from ..conferencia.cadastro import Bate, comparar_com_cadastro
from ..conferencia.padroes import SituacaoPadrao
from .estilo import AMARELO, VERDE
from .servico import Analise, descrever_padroes, descrever_pontos

VERMELHO = "#c62828"
LARGURA_DESENHO = 2480  # A4 a 300 dpi: os checks saem nítidos mesmo com zoom


@dataclass
class Marca:
    caixa: tuple[float, float, float, float]  # em fração da página
    cor: str
    simbolo: str  # "✓", "✗" ou "!"
    faixa: bool  # True: faixa translúcida atrás da linha (pontos); False: só o contorno


def _marca_do_resultado(resultado: Resultado) -> tuple[str, str]:
    return {Resultado.APROVADO: (VERDE, "✓"),
            Resultado.REPROVADO: (VERMELHO, "✗")}.get(resultado, (AMARELO, "!"))


def lido_para_cadastro(analise: Analise) -> dict[str, str | None]:
    """O que foi lido no certificado para comparar com o cadastro (o digitado à mão vale mais
    que o lido) — o mesmo que a caixa "Instrumento" da tela mostra."""
    conferencia = analise.conferencia
    lido = {chave: analise.campos.get(chave) or None for chave, _ in CAMPOS_CADASTRO}
    if conferencia and conferencia.codigo:
        lido["codigo"] = conferencia.codigo
    if conferencia and conferencia.faixa_certificado:
        lido["faixa"] = conferencia.faixa_certificado
    lido.update({chave: analise.manual[chave] for chave in ("codigo", "faixa")
                 if analise.manual.get(chave)})
    return lido


def _caixa_do_rotulo(analise: Analise, rotulo: str) -> tuple[float, float, float, float] | None:
    """O retângulo que junta as palavras com esse rótulo (ex.: todas as do "fabricante")."""
    caixas = [p.caixa for i, p in enumerate(analise.pagina.palavras)
              if analise.rotulos[i] == rotulo]
    if not caixas:
        return None
    return (min(c[0] for c in caixas), min(c[1] for c in caixas),
            max(c[2] for c in caixas), max(c[3] for c in caixas))


def marcas_da_analise(analise: Analise) -> list[Marca]:
    conferencia = analise.conferencia
    if conferencia is None:
        return []
    marcas: list[Marca] = []
    for linha in descrever_pontos(conferencia, analise):
        cor, simbolo = _marca_do_resultado(linha.resultado)
        marcas.append(Marca(linha.caixa, cor, simbolo, faixa=True))
    for linha in descrever_padroes(conferencia):
        if linha.caixa is None:
            continue
        cor, simbolo = {SituacaoPadrao.EM_DIA: (VERDE, "✓"),
                        SituacaoPadrao.VENCIDO: (VERMELHO, "✗")}.get(
            linha.situacao, (AMARELO, "!"))
        marcas.append(Marca(linha.caixa, cor, simbolo, faixa=False))
    for item in comparar_com_cadastro(conferencia.cadastro, lido_para_cadastro(analise)):
        if item.bate == Bate.SEM_DADO:
            continue
        caixa = _caixa_do_rotulo(analise, item.chave)
        if caixa is not None:
            cor, simbolo = (VERDE, "✓") if item.bate == Bate.SIM else (VERMELHO, "✗")
            marcas.append(Marca(caixa, cor, simbolo, faixa=False))
    return marcas


def _fonte(tamanho: int) -> ImageFont.ImageFont:
    for nome in ("C:/Windows/Fonts/seguisym.ttf", "C:/Windows/Fonts/seguisb.ttf",
                 "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(tamanho)


def _rgb(cor: str, alfa: int = 255) -> tuple[int, int, int, int]:
    cor = cor.lstrip("#")
    return int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16), alfa


def desenhar_marcas(marcas: list[Marca], proporcao: float) -> Image.Image:
    """Imagem transparente (largura fixa, altura = largura × `proporcao`) com as marcas."""
    largura = LARGURA_DESENHO
    altura = round(largura * proporcao)
    camada = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    sombra = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    ds = ImageDraw.Draw(sombra)
    for m in marcas:
        e, t, dr, b = (m.caixa[0] * largura, m.caixa[1] * altura,
                       m.caixa[2] * largura, m.caixa[3] * altura)
        alto = b - t
        lado = max(alto * (1.2 if m.faixa else 1.3), 40.0)
        x = min(dr + 20, largura - lado - 8)
        cy = (t + b) / 2
        if m.faixa:  # a linha inteira do ponto, translúcida, até o check
            d.rectangle((e - 12, t - 2, x + lado + 8, b + 2), fill=_rgb(m.cor, 55),
                        outline=_rgb(m.cor), width=6)
        else:
            d.rectangle((e - 8, t - 4, dr + 8, b + 4), outline=_rgb(m.cor), width=5)
        ds.ellipse((x + 4, cy - lado / 2 + 4, x + lado + 12, cy + lado / 2 + 12),
                   fill=(0, 0, 0, 170))
        d.ellipse((x - 4, cy - lado / 2 - 4, x + lado + 4, cy + lado / 2 + 4), fill="#000000")
        d.ellipse((x, cy - lado / 2, x + lado, cy + lado / 2), fill=_rgb(m.cor),
                  outline="#ffffff", width=5)
        letra = "#000000" if m.simbolo == "!" else "#ffffff"
        d.text((x + lado / 2, cy), m.simbolo, font=_fonte(round(lado * 0.8)), fill=letra,
               anchor="mm", stroke_width=2, stroke_fill=letra)
    sombra = sombra.filter(ImageFilter.GaussianBlur(8))
    return Image.alpha_composite(sombra, camada)
