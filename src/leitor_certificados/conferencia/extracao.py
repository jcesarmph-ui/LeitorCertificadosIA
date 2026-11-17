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


# Ângulo em graus e minutos (goniômetro): "14°59'", "-0°01'", "90°00'" (decisão do usuário,
# 2026-11-16: no goniômetro é sempre graus°minutos'). Vira graus decimais: 14°59' = 14,9833°.
_GRAUS_MINUTOS = re.compile(r"^([+\-]?)(\d+)°(\d{1,2})['’′]?$")


def para_numero(texto: str) -> float | None:
    """"-0,001" → -0.001; "+1.350,00" → 1350.0; "14°59'" → 14.9833; "abc" → None.
    Um só separador é decimal."""
    t = "".join(texto.split()).replace("−", "-").replace("±", "")
    if m := _GRAUS_MINUTOS.match(t):
        graus = int(m[2]) + int(m[3]) / 60
        return round(-graus if m[1] == "-" else graus, 9)
    if "," in t and "." in t:  # o último separador é o decimal; o outro é de milhar
        decimal = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    else:
        t = t.replace(",", ".")
    return float(t) if _NUMERO.match(t) else None


_ESCALA = re.compile(r"HR\s?(\d{2}\s?[TN]|[A-HK]|[TN])W?", re.IGNORECASE)


def escala_de_dureza(texto: str) -> str | None:
    """A escala de dureza escrita no texto, do jeito da empresa: "HR15TW" → "HR15T",
    "HRBW" → "HRB", "hrc" → "HRC". O "W" (esfera de carboneto) que o laboratório põe é
    ignorado (o usuário: "nós aqui não usamos"). None se não houver escala."""
    achou = _ESCALA.search(texto.replace(" ", ""))
    return ("HR" + achou.group(1).replace(" ", "")).upper() if achou else None


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
    # todos os números que o modelo marcou como nominal na linha (às vezes marca dois, ex.:
    # "30,00" e "29,95"): a conferência usa o que existir no plano
    nominais: tuple[float, ...] = ()
    # a linha veio em graus°minutos' (goniômetro): a tela mostra assim, sem converter
    graus_minutos: bool = False
    # escala de dureza da linha (durômetro: "HR15T", "HRB", "HRC"), sem o "W" do laboratório
    escala: str | None = None


@dataclass(frozen=True)
class PadraoLido:
    """Um padrão da tabela "Padrões" (etapa 8): a identificação e a validade, como escritas."""

    codigo: str | None
    validade: str | None
    caixa: tuple[float, float, float, float]


@dataclass(frozen=True)
class CertificadoLido:
    codigo: str | None
    pontos: list[PontoLido]
    textos: tuple[str, ...] = ()  # as palavras da folha na ordem de leitura (procurar o código)
    faixa: str | None = None  # a faixa lida, ex.: "0 mm | 500 mm"
    data_calibracao: str | None = None  # como está escrita ("12/08/2026")
    padroes: tuple[PadraoLido, ...] = ()


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


def _valor_da_coluna(textos: list[tuple[str, float]]) -> str:
    """`textos` = [(texto, certeza do modelo), …] das palavras da linha com o mesmo rótulo.

    Um número dividido em pedaços ("1 350,00") é juntado. Mas, se o modelo marcou dois números
    diferentes com o mesmo rótulo (ex.: "7,941" e "0,004" como incerteza), juntar dá um texto
    que não é número: fica o número em que o modelo tem **mais certeza**."""
    junto = " ".join(t for t, _ in textos)
    if para_numero(junto) is not None:
        return junto
    numeros = [(c, t) for t, c in textos if para_numero(t) is not None]
    return max(numeros)[1] if numeros else junto


def montar_padroes(pagina: Pagina, rotulos: list[str]) -> tuple[PadraoLido, ...]:
    """As palavras `padrao.codigo` e `padrao.validade` de uma mesma linha formam um padrão.

    Uma linha pode ter dois padrões lado a lado (tabela em duas metades): um código novo depois
    de outro código já começa outro padrão. Validade com várias palavras ("12 de agosto de
    2026") é juntada."""
    marcadas = {id(p): r for p, r in zip(pagina.palavras, rotulos, strict=True)
                if r in ("padrao.codigo", "padrao.validade")}
    padroes: list[PadraoLido] = []
    for linha in _linhas(pagina.palavras):
        atual: dict[str, list[Palavra]] = {}
        grupos: list[dict[str, list[Palavra]]] = []
        for p in sorted((q for q in linha if id(q) in marcadas), key=lambda q: q.caixa[0]):
            tipo = marcadas[id(p)].removeprefix("padrao.")
            if tipo == "codigo" and "codigo" in atual and "validade" in atual:
                grupos.append(atual)
                atual = {}
            atual.setdefault(tipo, []).append(p)
        if atual:
            grupos.append(atual)
        for grupo in grupos:
            todas = [p for lista in grupo.values() for p in lista]
            padroes.append(PadraoLido(
                codigo=" ".join(p.texto for p in grupo.get("codigo", [])) or None,
                validade=" ".join(p.texto for p in grupo.get("validade", [])) or None,
                caixa=(min(p.caixa[0] for p in todas), min(p.caixa[1] for p in todas),
                       max(p.caixa[2] for p in todas), max(p.caixa[3] for p in todas))))
    return tuple(padroes)


def montar_certificado(modelo: Pipeline, pagina: Pagina, limiar: float = LIMIAR_CERTEZA,
                       previsoes: list[tuple[str, float]] | None = None) -> CertificadoLido:
    """Usa o modelo para achar o código do instrumento e os pontos da tabela. Palavras com
    certeza abaixo do `limiar` não entram (ficam como "outro"). `previsoes` já prontas (com as
    correções da pessoa no lugar do palpite) evitam perguntar ao modelo de novo."""
    previsoes = com_limiar(previsoes or prever(modelo, pagina), limiar)
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

    da_tabela: list[tuple[Palavra, str, float]] = [
        (p, rotulo.removeprefix("ponto."), certeza)
        for p, (rotulo, certeza) in zip(pagina.palavras, previsoes, strict=True)
        if rotulo.startswith("ponto.")
    ]
    rotulo_de = {id(p): t for p, t, _ in da_tabela}
    certeza_de = {id(p): c for p, _, c in da_tabela}
    pontos: list[PontoLido] = []
    for linha in _linhas(pagina.palavras):
        da_linha = [p for p in linha if id(p) in rotulo_de]
        if len(da_linha) < 2:
            continue
        textos: dict[str, list[tuple[str, float]]] = {}
        for p in sorted(da_linha, key=lambda q: q.caixa[0]):
            textos.setdefault(rotulo_de[id(p)], []).append((p.texto, certeza_de[id(p)]))
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
            nominais=tuple(n for t, _ in textos.get("nominal", [])
                           if (n := para_numero(t)) is not None),
            encontrado=para_numero(valores.get("encontrado", "")),
            erro=para_numero(valores.get("erro", "")),
            incerteza=para_numero(valores.get("incerteza", "")),
            caixa=(esq, min(p.caixa[1] for p in da_linha), dir_,
                   max(p.caixa[3] for p in da_linha)),
            numeros=numeros,
            erro_maximo=para_numero(valores.get("erro_maximo", "")),
            criterio=para_numero(valores.get("criterio", "")),
            graus_minutos=any(_GRAUS_MINUTOS.match("".join(p.texto.split()).replace("−", "-"))
                              for p in da_linha),
            escala=next((e for p in sorted(linha, key=lambda q: q.caixa[0])
                         if (e := escala_de_dureza(p.texto))), None),
        ))
    ordem = sorted(pagina.palavras, key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
    data_palavras = sorted(
        (p for p, (rotulo, _) in zip(pagina.palavras, previsoes, strict=True)
         if rotulo == "data_calibracao"),
        key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
    return CertificadoLido(
        codigo, pontos, tuple(p.texto for p in ordem), faixa,
        data_calibracao=" ".join(p.texto for p in data_palavras) or None,
        padroes=_padroes(pagina, [r for r, _ in previsoes]))


def _padroes(pagina: Pagina, rotulos: list[str]) -> tuple[PadraoLido, ...]:
    """Os padrões pela tabela (quantos são e a validade de cada um; o código não importa,
    pedido do usuário de 2026-11-17). Sem a tabela, pelo que o modelo marcou."""
    from .tabela_padroes import padroes_por_regra

    tabela = padroes_por_regra(pagina)
    if tabela is None:
        return montar_padroes(pagina, rotulos)
    return tuple(PadraoLido(codigo=None, validade=v, caixa=c) for v, c in tabela)
