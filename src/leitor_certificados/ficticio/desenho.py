"""Escreve o PDF digital de um certificado fictício e anota onde ficou cada informação.

A anotação ("campos") é a parte mais importante para o machine learning: para cada texto que é
uma resposta (nº do certificado, data, valores dos pontos…) guardamos **o que é** e **a caixa**
onde ele está na página. Assim, na etapa 3, o modelo pode aprender "este pedaço de texto é a data
da calibração" e ser corrigido quando errar.

Caixa = [esquerda, topo, direita, base], em fração da página (0 a 1, origem no canto superior
esquerdo), para valer em qualquer resolução — no PDF digital e na imagem escaneada.
"""

from __future__ import annotations

import random
from pathlib import Path

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .dados import Certificado
from .laboratorios import (
    ENCONTRADO,
    ERRO,
    INCERTEZA,
    INDICE,
    NOMINAL,
    Laboratorio,
    formatar_data,
    formatar_numero,
)

LARGURA, ALTURA = A4
MARGEM = 50
CINZA = Color(0.45, 0.45, 0.45)
FAIXA = Color(0.18, 0.28, 0.42)

_FONTES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold"),
    "Times": ("Times-Roman", "Times-Bold"),
    "Courier": ("Courier", "Courier-Bold"),
}


class _Pagina:
    """Desenha na página e guarda a caixa de cada texto que é uma resposta."""

    def __init__(self, canvas: Canvas, fonte: str, dx: float, dy: float):
        self.c = canvas
        self.normal, self.negrito = _FONTES[fonte]
        self.dx, self.dy = dx, dy  # pequeno deslocamento sorteado: nada fica sempre no mesmo lugar
        self.campos: list[dict] = []

    def texto(self, x: float, y: float, s: str, tam: float = 10, negrito: bool = False,
              alinhar: str = "esquerda", cor=black, campo: str | None = None,
              ponto: int | None = None) -> float:
        fonte = self.negrito if negrito else self.normal
        largura = stringWidth(s, fonte, tam)
        x += self.dx
        y += self.dy
        if alinhar == "centro":
            x -= largura / 2
        elif alinhar == "direita":
            x -= largura
        self.c.setFont(fonte, tam)
        self.c.setFillColor(cor)
        self.c.drawString(x, y, s)
        if campo:
            anotacao = {
                "campo": campo,
                "texto": s,
                "caixa": [
                    round(x / LARGURA, 4),
                    round((ALTURA - (y + 0.78 * tam)) / ALTURA, 4),
                    round((x + largura) / LARGURA, 4),
                    round((ALTURA - (y - 0.24 * tam)) / ALTURA, 4),
                ],
            }
            if ponto is not None:
                anotacao["ponto"] = ponto
            self.campos.append(anotacao)
        return largura

    def linha(self, x0: float, y0: float, x1: float, y1: float, espessura: float = 0.7):
        self.c.setLineWidth(espessura)
        self.c.setStrokeColor(black)
        self.c.line(x0 + self.dx, y0 + self.dy, x1 + self.dx, y1 + self.dy)

    def retangulo(self, x: float, y: float, w: float, h: float, preencher=None):
        self.c.setStrokeColor(black)
        self.c.setLineWidth(0.7)
        if preencher is not None:
            self.c.setFillColor(preencher)
        self.c.rect(x + self.dx, y + self.dy, w, h, stroke=1, fill=preencher is not None)


def _valor_info(cert: Certificado, lab: Laboratorio, chave: str) -> str:
    if chave in ("data_calibracao", "data_emissao"):
        return formatar_data(getattr(cert, chave), lab.formato_data)
    if chave == "faixa":
        casas = 0 if cert.faixa_min.is_integer() and cert.faixa_max.is_integer() else cert.casas
        minimo = formatar_numero(cert.faixa_min, casas, lab.decimal)
        maximo = formatar_numero(cert.faixa_max, casas, lab.decimal)
        return f"{minimo} {lab.palavra_faixa} {maximo} {cert.unidade}"
    if chave == "resolucao":
        return f"{formatar_numero(cert.resolucao, cert.casas, lab.decimal)} {cert.unidade}"
    if chave == "temperatura":
        return f"{formatar_numero(cert.temperatura, 1, lab.decimal)} °C"
    if chave == "umidade":
        return f"{cert.umidade} %"
    return str(getattr(cert, chave))


def _cabecalho(p: _Pagina, cert: Certificado, lab: Laboratorio) -> float:
    """Desenha o topo; devolve a altura (y) onde o resto começa."""
    topo = ALTURA - MARGEM
    rotulo = lab.rotulos["numero"]
    if lab.cabecalho == "centro":
        p.texto(LARGURA / 2, topo, lab.nome, 15, True, "centro", campo="laboratorio")
        p.texto(LARGURA / 2, topo - 15, lab.endereco, 8.5, alinhar="centro", cor=CINZA)
        p.linha(MARGEM, topo - 24, LARGURA - MARGEM, topo - 24, 1.2)
        p.texto(LARGURA / 2, topo - 48, lab.titulo, 13, True, "centro")
        largura = p.texto(LARGURA - MARGEM, topo - 66, cert.numero, 11, True, "direita",
                          campo="numero_certificado")
        p.texto(LARGURA - MARGEM - largura - 4, topo - 66, rotulo, 11, alinhar="direita")
        return topo - 90
    if lab.cabecalho == "faixa":
        p.retangulo(MARGEM - 10, topo - 34, LARGURA - 2 * MARGEM + 20, 46, preencher=FAIXA)
        p.texto(MARGEM, topo - 12, lab.nome, 14, True, cor=white, campo="laboratorio")
        p.texto(MARGEM, topo - 26, lab.endereco, 8, cor=white)
        p.texto(LARGURA - MARGEM, topo - 12, lab.titulo, 12, True, "direita", cor=white)
        largura = p.texto(LARGURA - MARGEM, topo - 26, cert.numero, 10, True, "direita",
                          cor=white, campo="numero_certificado")
        p.texto(LARGURA - MARGEM - largura - 4, topo - 26, rotulo, 10, alinhar="direita",
                cor=white)
        return topo - 62
    # "esquerda": nome do laboratório à esquerda, título e número à direita
    p.texto(MARGEM, topo, lab.nome, 13, True, campo="laboratorio")
    p.texto(MARGEM, topo - 13, lab.endereco, 8, cor=CINZA)
    p.texto(LARGURA - MARGEM, topo - 36, lab.titulo, 11, True, "direita")
    largura = p.texto(LARGURA - MARGEM, topo - 52, cert.numero, 11, True, "direita",
                      campo="numero_certificado")
    p.texto(LARGURA - MARGEM - largura - 4, topo - 52, rotulo + ":", 11, alinhar="direita")
    p.linha(MARGEM, topo - 62, LARGURA - MARGEM, topo - 62)
    return topo - 84


def _informacoes(p: _Pagina, cert: Certificado, lab: Laboratorio, y: float) -> float:
    if lab.info == "lista":
        for chave in lab.ordem_info:
            largura = p.texto(MARGEM, y, lab.rotulos[chave] + ":", 10, True)
            p.texto(MARGEM + max(largura + 6, 150), y, _valor_info(cert, lab, chave), 10,
                    campo=chave)
            y -= 15
        return y - 10
    # "grade": duas colunas dentro de um quadro
    meia = (LARGURA - 2 * MARGEM) / 2
    linhas = (len(lab.ordem_info) + 1) // 2
    altura = linhas * 26 + 14
    p.retangulo(MARGEM - 6, y - altura + 12, LARGURA - 2 * MARGEM + 12, altura)
    for n, chave in enumerate(lab.ordem_info):
        x = MARGEM + (n % 2) * meia
        yy = y - (n // 2) * 26
        p.texto(x, yy, lab.rotulos[chave], 7.5, cor=CINZA)
        p.texto(x, yy - 11, _valor_info(cert, lab, chave), 10, True, campo=chave)
    return y - altura - 6


def _tabela(p: _Pagina, cert: Certificado, lab: Laboratorio, y: float) -> float:
    colunas = lab.colunas
    largura = (LARGURA - 2 * MARGEM) / len(colunas)
    altura_linha = 17
    p.retangulo(MARGEM, y - 6, LARGURA - 2 * MARGEM, altura_linha + 4, preencher=Color(.9, .9, .9))
    for n, coluna in enumerate(colunas):
        titulo = lab.titulos_colunas[coluna]
        if coluna not in (INDICE, "k"):
            titulo += f" ({cert.unidade})"
        tam = 8.5
        while stringWidth(titulo, p.negrito, tam) > largura - 6:  # título comprido: letra menor
            tam -= 0.5
        p.texto(MARGEM + largura * (n + 0.5), y, titulo, tam, True, "centro")
    y -= altura_linha + 4
    for i, ponto in enumerate(cert.pontos):
        valores = {
            INDICE: str(i + 1),
            NOMINAL: formatar_numero(ponto.nominal, cert.casas, lab.decimal),
            ENCONTRADO: formatar_numero(ponto.encontrado, cert.casas, lab.decimal),
            ERRO: formatar_numero(ponto.erro, cert.casas, lab.decimal, lab.sinal_mais),
            INCERTEZA: formatar_numero(ponto.incerteza, cert.casas + 1, lab.decimal),
            "k": formatar_numero(ponto.k, 2, lab.decimal),
        }
        for n, coluna in enumerate(colunas):
            campo = None if coluna == INDICE else f"ponto.{coluna}"
            p.texto(MARGEM + largura * (n + 0.5), y, valores[coluna], 10, alinhar="centro",
                    campo=campo, ponto=i if campo else None)
        p.linha(MARGEM, y - 6, LARGURA - MARGEM, y - 6, 0.3)
        y -= altura_linha
    return y - 14


def _rodape(p: _Pagina, cert: Certificado, lab: Laboratorio, y: float):
    p.texto(MARGEM, y, lab.nota, 8.5, cor=CINZA)
    y -= 50
    p.linha(MARGEM, y, MARGEM + 200, y)
    p.texto(MARGEM, y - 12, cert.tecnico, 10, campo="tecnico")
    p.texto(MARGEM, y - 24, lab.rotulos["tecnico"], 8.5, cor=CINZA)
    p.texto(LARGURA / 2, 30, "DOCUMENTO FICTÍCIO - gerado para estudo de machine learning, "
            "sem validade.", 7.5, alinhar="centro", cor=CINZA)


def desenhar(cert: Certificado, destino: Path, rng: random.Random) -> list[dict]:
    """Escreve o PDF digital em `destino` e devolve os campos anotados."""
    lab = cert.lab
    canvas = Canvas(str(destino), pagesize=A4, invariant=1)  # invariant: mesmo arquivo sempre
    canvas.setTitle(f"Certificado fictício {cert.id}")
    p = _Pagina(canvas, lab.fonte, rng.uniform(-8, 8), rng.uniform(-12, 4))
    y = _cabecalho(p, cert, lab)
    y = _informacoes(p, cert, lab, y)
    y = _tabela(p, cert, lab, y)
    _rodape(p, cert, lab, y)
    canvas.showPage()
    canvas.save()
    return p.campos
