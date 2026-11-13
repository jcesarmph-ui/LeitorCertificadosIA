"""Transforma cada palavra numa lista de **pistas** (atributos) para o modelo aprender.

O modelo não enxerga a folha; só recebe pistas. Para saber **o que** uma palavra é — e não
decorar **onde** ela fica —, as pistas são de quatro tipos:

1. **Como a palavra é escrita**: só dígitos? tem vírgula? barra? letras maiúsculas? ("28/mai/2025"
   tem o jeito de data; "0,0012" tem o jeito de medida).
2. **O que há ao lado e em cima**: as palavras à esquerda na mesma linha ("Data da calibração:")
   e as de texto mais próximas acima (o título da coluna). Também **pedaços de letras** das
   palavras vizinhas ("emiss" vale para "emissão" e "emitido"), para o modelo reconhecer um
   rótulo que nunca viu escrito daquele jeito.
3. **O que os números fazem na tabela** — a pista mais forte contra o "decorar": numa linha de
   medição, o *erro* é a diferença entre dois outros números ("encontrado − nominal"); o
   *nominal* cresce de cima para baixo; o *k* é o mesmo em todas as linhas; a *incerteza* é
   sempre positiva e pequena; o *erro máximo* é |erro| + U (ADR 0009).
   Isso vale para qualquer laboratório, com qualquer nome de coluna.
4. **Onde está** (aproximadamente): fração da folha e tamanho da letra. É pista fraca de
   propósito: cada laboratório monta a folha de um jeito.
"""

from __future__ import annotations

import re
import unicodedata

from ..leitura import Pagina, Palavra

_NUMERO = re.compile(r"^[+\-−]?\d+(?:[.,]\d+)?$")


def _normalizar(texto: str) -> str:
    """Palavra → forma de comparar: minúscula, sem acento e sem pontuação nas pontas."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip(" :.;,()")


def _forma(texto: str) -> str:
    """O "jeito" do texto: dígitos viram d, letras viram a/A, o resto fica. Repetições somem."""
    f = re.sub(r"\d", "d", texto)
    f = re.sub(r"[a-zà-ÿ]", "a", f)
    f = re.sub(r"[A-ZÀ-ß]", "A", f)
    return re.sub(r"(.)\1+", r"\1\1", f)


def _pista(texto: str) -> str:
    """Vira pista de contexto: palavra de texto vale por ela mesma; número vale pelo jeito."""
    if sum(c.isalpha() for c in texto) >= 2:
        return _normalizar(texto)
    return "#" + _forma(texto)


def _tem_texto(palavra: Palavra) -> bool:
    return sum(c.isalpha() for c in palavra.texto) >= 2


def _trincas(texto: str) -> set[str]:
    """Pedaços de 3 letras ("calibração" → cal, ali, lib…): palavras parentes dividem pedaços."""
    n = _normalizar(texto)
    return {n[i:i + 3] for i in range(len(n) - 2)}


def _valor(texto: str) -> float | None:
    """O número escrito na palavra (com vírgula ou ponto decimal), ou None se não for número."""
    t = texto.strip()
    if not _NUMERO.match(t):
        return None
    return float(t.replace("−", "-").replace(",", "."))


def _casas(texto: str) -> int:
    t = texto.strip().replace(",", ".")
    return len(t.split(".")[1]) if "." in t else 0


def _redondo(v: float) -> bool:
    """Número "redondo" (0, 2, 50, 0,5, 12,5…): poucas casas significativas."""
    return abs(v * 4 - round(v * 4)) < 1e-9 or abs(v / 5 - round(v / 5)) < 1e-9


def _altura(p: Palavra) -> float:
    return p.caixa[3] - p.caixa[1]


def _agrupar_linhas(palavras: list[Palavra]) -> list[int]:
    """Número da linha de cada palavra (palavras com o centro na mesma altura)."""
    ordem = sorted(range(len(palavras)), key=lambda i: palavras[i].centro[1])
    linha_de = [0] * len(palavras)
    atual = -1
    y_ref = None
    h_ref = 0.0
    for i in ordem:
        p = palavras[i]
        if y_ref is None or abs(p.centro[1] - y_ref) > 0.6 * max(h_ref, _altura(p)):
            atual += 1
            y_ref, h_ref = p.centro[1], _altura(p)
        linha_de[i] = atual
    return linha_de


def _sobrepoe_x(a: Palavra, b: Palavra) -> bool:
    return min(a.caixa[2], b.caixa[2]) - max(a.caixa[0], b.caixa[0]) > 0


def _pistas_de_tabela(i: int, palavras: list[Palavra], linha_de: list[int],
                      numericas: dict[int, float], linhas_tabela: set[int]) -> dict[str, float]:
    """O que o número faz na tabela: diferença de outros dois, coluna crescente/constante…"""
    pistas: dict[str, float] = {}
    p = palavras[i]
    v = numericas[i]
    linha = [j for j in numericas if linha_de[j] == linha_de[i]]
    pistas["n_num_linha"] = min(len(linha), 8) / 8
    if linha_de[i] not in linhas_tabela:
        return pistas
    ordenados = sorted(linha, key=lambda j: palavras[j].centro[0])
    pistas[f"col_na_linha={min(ordenados.index(i), 6)}"] = 1.0
    pistas[f"col_da_direita={min(len(ordenados) - 1 - ordenados.index(i), 6)}"] = 1.0

    # erro = (um outro número da linha) − (outro número da linha)?
    tol = 1.6 * 10 ** -_casas(p.texto)
    outros = [numericas[j] for j in linha if j != i]
    pistas["e_diferenca"] = float(any(
        abs((b - a) - v) <= tol for a in outros for b in outros if a is not b
    ))
    pistas["e_igual_a_outro"] = float(any(abs(o - v) <= tol for o in outros))
    # erro máximo = |erro| + U: a soma de um número da linha (sem sinal) com outro positivo
    pistas["e_soma_abs"] = float(v > 0 and any(
        abs((abs(a) + b) - v) <= tol for a in outros for b in outros
        if a is not b and b > 0 and a != 0
    ))

    # tamanho do número em relação aos outros da linha (0 = o menor, 1 = o maior)
    magnitudes = sorted(abs(o) for o in outros + [v])
    pistas["rank_magnitude"] = magnitudes.index(abs(v)) / max(len(magnitudes) - 1, 1)
    pistas["e_redondo"] = float(_redondo(v))
    pistas["e_zero"] = float(v == 0)
    pistas["e_negativo"] = float(v < 0 or p.texto.strip().startswith(("-", "−")))
    pistas["tem_sinal_mais"] = float(p.texto.strip().startswith("+"))

    # a coluna toda (números das outras linhas da tabela, na mesma posição horizontal)
    coluna = sorted(
        (j for j in numericas if linha_de[j] in linhas_tabela and _sobrepoe_x(p, palavras[j])),
        key=lambda j: palavras[j].centro[1],
    )
    valores = [numericas[j] for j in coluna]
    if len(valores) >= 3:
        pares = list(zip(valores, valores[1:], strict=False))
        pistas["col_crescente"] = float(all(b > a for a, b in pares))
        pistas["col_constante"] = float(len(set(valores)) == 1)
        pistas["col_tem_negativo"] = float(any(x < 0 for x in valores))
        pistas["col_toda_positiva"] = float(all(x > 0 for x in valores))
        pistas["col_inteiros"] = float(all(float(x).is_integer() for x in valores))
        pistas["col_sequencial"] = float(all(abs((b - a) - 1) < 1e-9
                                             for a, b in zip(valores, valores[1:], strict=False)))
        pistas["col_poucos_valores"] = float(len(set(valores)) <= 3)
        pistas["pos_na_col_primeira"] = float(coluna[0] == i)
        pistas["pos_na_col_ultima"] = float(coluna[-1] == i)
        # o nominal é "redondo" e anda em passos regulares; o valor encontrado tem "ruído"
        redondos = sum(_redondo(x) for x in valores) / len(valores)
        pistas["col_redonda"] = redondos
        passos = [round(b - a, 9) for a, b in zip(valores, valores[1:], strict=False)]
        pistas["col_passo_regular"] = float(len(set(passos)) == 1)
        pistas["col_passo_quase_regular"] = float(
            max(passos) - min(passos) <= 0.25 * max(abs(max(passos)), 1e-9))
    return pistas


def atributos_da_pagina(pagina: Pagina) -> list[dict[str, float | str]]:
    """Uma lista de pistas por palavra, na mesma ordem de `pagina.palavras`."""
    palavras = pagina.palavras
    linha_de = _agrupar_linhas(palavras)
    numericas = {i: v for i, p in enumerate(palavras) if (v := _valor(p.texto)) is not None}
    por_linha: dict[int, int] = {}
    for i in numericas:
        por_linha[linha_de[i]] = por_linha.get(linha_de[i], 0) + 1
    linhas_tabela = {ln for ln, q in por_linha.items() if q >= 3}
    alturas = sorted(_altura(p) for p in palavras) or [0.0]
    altura_tipica = alturas[len(alturas) // 2] or 1e-6

    resultado: list[dict[str, float | str]] = []
    for i, p in enumerate(palavras):
        texto = p.texto
        n = max(len(texto), 1)
        pistas: dict[str, float | str] = {
            "forma=" + _forma(texto): 1.0,
            "tamanho": min(len(texto), 40) / 40,
            "frac_digitos": sum(c.isdigit() for c in texto) / n,
            "frac_maiusc": sum(c.isupper() for c in texto) / n,
            "tem_virgula": float("," in texto),
            "tem_ponto": float("." in texto),
            "tem_barra": float("/" in texto),
            "tem_traco": float("-" in texto),
            "tem_pct": float("%" in texto),
            "tem_grau": float("°" in texto),
            "tem_dois_pontos": float(":" in texto),
            "x": p.centro[0],
            "y": p.centro[1],
            "largura": p.caixa[2] - p.caixa[0],
            "altura_rel": min(_altura(p) / altura_tipica, 3.0) / 3.0,
        }
        if _tem_texto(p):
            pistas["palavra=" + _normalizar(texto)] = 1.0
            for t in _trincas(texto):
                pistas["eu3=" + t] = 1.0

        # --- à esquerda, na mesma linha (do mais perto para o mais longe)
        esquerda = sorted(
            (q for j, q in enumerate(palavras)
             if j != i and linha_de[j] == linha_de[i] and q.centro[0] < p.centro[0]),
            key=lambda q: -q.centro[0],
        )
        for k, q in enumerate(esquerda[:3], start=1):
            pistas[f"esq{k}=" + _pista(q.texto)] = 1.0
        for q in esquerda[:6]:
            if _tem_texto(q):
                pistas["esq_qq=" + _normalizar(q.texto)] = 1.0
                for t in _trincas(q.texto):
                    pistas["esq3=" + t] = 1.0
        pistas["n_esq"] = min(len(esquerda), 12) / 12
        pistas["n_num_esq"] = min(sum(not _tem_texto(q) for q in esquerda), 8) / 8

        # --- em cima, na mesma coluna: as palavras de texto mais próximas
        acima = sorted(
            (q for q in palavras
             if _tem_texto(q) and q.caixa[3] <= p.centro[1] and _sobrepoe_x(p, q)),
            key=lambda q: p.centro[1] - q.centro[1],
        )
        for k, q in enumerate(acima[:2], start=1):
            pistas[f"acima{k}=" + _normalizar(q.texto)] = 1.0
            pistas["dist_acima1" if k == 1 else "dist_acima2"] = min(
                p.centro[1] - q.centro[1], 0.3
            ) / 0.3
            for t in _trincas(q.texto):
                pistas[f"acima{k}3=" + t] = 1.0
        if not acima:
            pistas["acima1=NADA"] = 1.0

        # --- o que o número faz na tabela
        if i in numericas:
            pistas.update(_pistas_de_tabela(i, palavras, linha_de, numericas, linhas_tabela))
        resultado.append(pistas)
    return resultado
