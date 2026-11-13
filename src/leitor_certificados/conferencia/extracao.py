"""Do resultado do modelo (rótulo de cada palavra) para os pontos medidos do certificado.

O modelo diz o que cada palavra é; aqui montamos a tabela: as palavras `ponto.nominal`,
`ponto.encontrado`, `ponto.erro` e `ponto.incerteza` que estão na mesma linha da folha formam um
ponto (com `ponto.erro_maximo` e `ponto.criterio`, quando o laboratório traz essas colunas).
Cada texto vira número (vírgula ou ponto decimal, com ou sem "+"/"−").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.pipeline import Pipeline

from ..aprendizado.modelo import LIMIAR_CERTEZA, com_limiar, prever
from ..leitura import Pagina, Palavra

_NUMERO = re.compile(r"^[+\-−]?\d+(?:[.,]\d+)?$")


def para_numero(texto: str) -> float | None:
    """"-0,001" → -0.001; "+1.350,00" → 1350.0; "abc" → None. Um só separador é decimal."""
    t = "".join(texto.split()).replace("−", "-").replace("±", "")
    if "," in t and "." in t:  # o último separador é o decimal; o outro é de milhar
        decimal = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    else:
        t = t.replace(",", ".")
    return float(t) if _NUMERO.match(t) else None


@dataclass(frozen=True)
class PontoLido:
    nominal: float
    encontrado: float | None
    erro: float | None
    incerteza: float | None
    caixa: tuple[float, float, float, float]  # a linha na folha (para desenhar o check)
    numeros: tuple[float, ...] = ()  # todos os números da linha, da esquerda para a direita
    erro_maximo: float | None = None  # |erro| + U, quando o laboratório informa (ADR 0009)
    criterio: float | None = None  # critério de aceitação ± do laboratório/cliente


@dataclass(frozen=True)
class CertificadoLido:
    codigo: str | None
    pontos: list[PontoLido]
    textos: tuple[str, ...] = ()  # as palavras da folha na ordem de leitura (procurar o código)
    faixa: str | None = None  # a faixa lida, ex.: "0 mm | 500 mm"


def _linhas(palavras: list[Palavra]) -> list[list[Palavra]]:
    ordenadas = sorted(palavras, key=lambda p: p.centro[1])
    linhas: list[list[Palavra]] = []
    for p in ordenadas:
        altura = p.caixa[3] - p.caixa[1]
        if linhas and abs(p.centro[1] - linhas[-1][0].centro[1]) <= 0.6 * max(altura, 1e-6):
            linhas[-1].append(p)
        else:
            linhas.append([p])
    return linhas


def _valor_da_coluna(textos: list[str]) -> str:
    """Um número dividido em pedaços ("1 350,00") é juntado. Mas, se o modelo marcou dois números
    diferentes da linha com o mesmo rótulo (ex.: "0,07" e "0,14" como incerteza), juntar dá um
    texto que não é número: fica o **primeiro** (o mais à esquerda) que for número."""
    junto = " ".join(textos)
    if para_numero(junto) is not None:
        return junto
    return next((t for t in textos if para_numero(t) is not None), junto)


def montar_certificado(modelo: Pipeline, pagina: Pagina,
                       limiar: float = LIMIAR_CERTEZA) -> CertificadoLido:
    """Usa o modelo para achar o código do instrumento e os pontos da tabela. Palavras com
    certeza abaixo do `limiar` não entram (ficam como "outro")."""
    previsoes = com_limiar(prever(modelo, pagina), limiar)
    codigo_palavras = [
        p for p, (rotulo, _) in zip(pagina.palavras, previsoes, strict=True) if rotulo == "codigo"
    ]
    codigo_palavras.sort(key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
    codigo = " ".join(p.texto for p in codigo_palavras) or None

    faixa_palavras = [
        p for p, (rotulo, _) in zip(pagina.palavras, previsoes, strict=True) if rotulo == "faixa"
    ]
    faixa_palavras.sort(key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
    faixa = " ".join(p.texto for p in faixa_palavras) or None

    da_tabela: list[tuple[Palavra, str]] = [
        (p, rotulo.removeprefix("ponto."))
        for p, (rotulo, _) in zip(pagina.palavras, previsoes, strict=True)
        if rotulo.startswith("ponto.")
    ]
    rotulo_de = {id(p): t for p, t in da_tabela}
    pontos: list[PontoLido] = []
    for linha in _linhas(pagina.palavras):
        da_linha = [p for p in linha if id(p) in rotulo_de]
        if len(da_linha) < 2:
            continue
        textos: dict[str, list[str]] = {}
        for p in sorted(da_linha, key=lambda q: q.caixa[0]):
            textos.setdefault(rotulo_de[id(p)], []).append(p.texto)
        valores = {tipo: _valor_da_coluna(lista) for tipo, lista in textos.items()}
        esq = min(p.caixa[0] for p in da_linha)
        dir_ = max(p.caixa[2] for p in da_linha)
        numeros = tuple(
            n for p in sorted(linha, key=lambda q: q.caixa[0])
            if esq <= p.centro[0] <= dir_ and (n := para_numero(p.texto)) is not None
        )
        nominal = para_numero(valores.get("nominal", ""))
        if nominal is None:
            if len(numeros) < 3:
                continue
            nominal = numeros[0]  # chute; o plano pode corrigir (reatribuição)
        pontos.append(PontoLido(
            nominal=nominal,
            encontrado=para_numero(valores.get("encontrado", "")),
            erro=para_numero(valores.get("erro", "")),
            incerteza=para_numero(valores.get("incerteza", "")),
            caixa=(esq, min(p.caixa[1] for p in da_linha), dir_,
                   max(p.caixa[3] for p in da_linha)),
            numeros=numeros,
            erro_maximo=para_numero(valores.get("erro_maximo", "")),
            criterio=para_numero(valores.get("criterio", "")),
        ))
    ordem = sorted(pagina.palavras, key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
    return CertificadoLido(codigo, pontos, tuple(p.texto for p in ordem), faixa)
