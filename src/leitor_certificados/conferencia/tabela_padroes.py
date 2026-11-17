"""A tabela dos padrões, lida por regra (pedido do usuário, 2026-11-17).

Para os padrões não é preciso ler tudo: basta saber **quantos padrões há** (uma linha da tabela
por padrão) e **se cada um tem uma validade em dia** na data da calibração. O código não importa.

Como acha:
1. o cabeçalho "Validade" / "Validity" / "Válido até" de uma coluna (o "Validade:" com
   dois-pontos é a validade do próprio certificado, não é coluna);
2. as linhas logo embaixo que têm texto em várias colunas do cabeçalho são os padrões (a linha
   de baixo só com a descrição em inglês não conta); a tabela acaba num espaço vazio maior;
3. a validade de cada linha é o que está na coluna "Validade".

Se não achar a tabela, quem lê os padrões continua sendo o modelo.
"""

from __future__ import annotations

import re
from statistics import median

from ..leitura import Pagina
from ..leitura.palavra import Palavra
from .padroes import ler_validade

_CABECALHO = re.compile(r"^(validade|validity|v[aá]lido|valid)$", re.IGNORECASE)


def _altura(p: Palavra) -> float:
    return p.caixa[3] - p.caixa[1]


def _mesma_linha(a: Palavra, b: Palavra) -> bool:
    return abs(a.centro[1] - b.centro[1]) <= 0.6 * max(_altura(a), _altura(b), 1e-6)


def _linhas(palavras: list[Palavra]) -> list[list[Palavra]]:
    linhas: list[list[Palavra]] = []
    for p in sorted(palavras, key=lambda q: q.centro[1]):
        if linhas and _mesma_linha(linhas[-1][0], p):
            linhas[-1].append(p)
        else:
            linhas.append([p])
    return [sorted(linha, key=lambda q: q.caixa[0]) for linha in linhas]


def _e_cabecalho(p: Palavra) -> bool:
    return bool(_CABECALHO.match(p.texto.strip().rstrip(".")))


def _colunas(cabecalho: list[Palavra]) -> list[tuple[float, float]]:
    """As faixas (esquerda, direita) de cada coluna do cabeçalho: palavras juntas ("Calibrado
    em") ficam na mesma coluna; a coluna vai até o começo da próxima."""
    grupos: list[list[Palavra]] = []
    for p in cabecalho:
        if grupos and p.caixa[0] - grupos[-1][-1].caixa[2] < 0.012:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    inicios = [g[0].caixa[0] for g in grupos]
    faixas = []
    for k in range(len(grupos)):
        esquerda = (inicios[k] + grupos[k - 1][-1].caixa[2]) / 2 if k else 0.0
        direita = (grupos[k][-1].caixa[2] + inicios[k + 1]) / 2 if k + 1 < len(grupos) else 1.0
        faixas.append((esquerda, direita))
    return faixas


def _coluna_de(x: float, faixas: list[tuple[float, float]]) -> int | None:
    for k, (e, d) in enumerate(faixas):
        if e <= x < d:
            return k
    return None


def padroes_por_regra(pagina: Pagina) -> list[tuple[str | None, tuple]] | None:
    """`ler_tabela_padroes` em cada folha (folha comprida: uma de cada vez), com as caixas de
    volta na medida da folha comprida. None se nenhuma folha tem a tabela."""
    from ..leitura.folhas import separar

    n = len(pagina.folhas)
    achados: list[tuple[str | None, tuple]] | None = None
    for k, (folha, _) in enumerate(separar(pagina)):
        tabela = ler_tabela_padroes(folha)
        if tabela is None:
            continue
        achados = achados or []
        for validade, (e, t, d, b) in tabela:
            achados.append((validade, (e, (k + t) / n, d, (k + b) / n) if n > 1 else (e, t, d, b)))
    return achados


def ler_tabela_padroes(pagina: Pagina) -> list[tuple[str | None, tuple]] | None:
    """[(validade escrita, caixa da linha), …] — um item por padrão, na ordem da tabela. None
    se a página não tem a tabela (nenhuma coluna "Validade" com data embaixo)."""
    palavras = pagina.palavras
    for titulo in (p for p in palavras if _e_cabecalho(p)):
        cabecalho = sorted((q for q in palavras if _mesma_linha(q, titulo)),
                           key=lambda q: q.caixa[0])
        faixas = _colunas(cabecalho)
        coluna = _coluna_de(titulo.centro[0], faixas)
        if coluna is None or len(faixas) < 3:
            continue
        minimo = max(2, len(faixas) // 2)  # uma linha de padrão tem texto em várias colunas
        abaixo = [q for q in palavras if q.centro[1] > titulo.caixa[3]
                  and q.centro[1] < titulo.centro[1] + 0.6]
        linhas: list[tuple[str | None, tuple]] = []
        alturas_y: list[float] = []
        anterior = titulo.centro[1]
        for linha in _linhas(abaixo):
            y = linha[0].centro[1]
            # espaço vazio bem maior que o de costume entre os padrões: a tabela acabou
            passo = median([b - a for a, b in zip(alturas_y, alturas_y[1:], strict=False)]) \
                if len(alturas_y) >= 2 else 4 * _altura(titulo)
            if linhas and y - anterior > 1.6 * passo:
                break
            if any(_e_cabecalho(q) for q in linha):  # o cabeçalho em inglês, logo embaixo
                anterior = y
                continue
            colunas = {c for q in linha if (c := _coluna_de(q.centro[0], faixas)) is not None}
            if len(colunas) < minimo:
                continue  # a descrição em inglês, embaixo da linha do padrão
            validade = " ".join(q.texto for q in linha
                                if _coluna_de(q.centro[0], faixas) == coluna) or None
            if linhas and validade and ler_validade(validade) is None:
                break  # na coluna da validade apareceu algo que não é data: acabou a tabela
            caixa = (min(q.caixa[0] for q in linha), min(q.caixa[1] for q in linha),
                     max(q.caixa[2] for q in linha), max(q.caixa[3] for q in linha))
            linhas.append((validade, caixa))
            alturas_y.append(y)
            anterior = y
        if linhas and any(ler_validade(v) for v, _ in linhas):
            return linhas
    return None
