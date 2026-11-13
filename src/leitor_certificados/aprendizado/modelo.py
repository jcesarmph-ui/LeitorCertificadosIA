"""O modelo de machine learning: aprende a dizer **o que cada palavra é**.

- `DictVectorizer` transforma as pistas de cada palavra numa tabela de números;
- `LogisticRegression` (scikit-learn) aprende quanto cada pista pesa para cada resposta.
  É um modelo simples, rápido e **explicável**: dá para ver quais pistas pesaram.

Treinar = mostrar muitas palavras com a resposta certa. Medir = pedir o palpite para palavras
de certificados que o modelo **nunca viu** e comparar com o gabarito.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ..leitura import Pagina
from .atributos import atributos_da_pagina
from .rotulos import OUTRO, rotular


def treinar(paginas: list[Pagina], campos_por_pagina: list[list[dict]],
            folga: float = 0.0) -> Pipeline:
    """Treina com páginas lidas + o gabarito de cada uma."""
    pistas: list[dict] = []
    respostas: list[str] = []
    for pagina, campos in zip(paginas, campos_por_pagina, strict=True):
        pistas += atributos_da_pagina(pagina)
        respostas += rotular(pagina, campos, folga)
    modelo = Pipeline([
        ("pistas", DictVectorizer()),
        ("classificador", LogisticRegression(C=20, max_iter=2000)),
    ])
    modelo.fit(pistas, respostas)
    return modelo


def prever(modelo: Pipeline, pagina: Pagina) -> list[tuple[str, float]]:
    """(rótulo, certeza) para cada palavra da página."""
    if not pagina.palavras:
        return []
    probabilidades = modelo.predict_proba(atributos_da_pagina(pagina))
    classes = modelo.classes_
    melhores = probabilidades.argmax(axis=1)
    return [(str(classes[m]), float(linha[m]))
            for m, linha in zip(melhores, probabilidades, strict=True)]


def ler_campos(modelo: Pipeline, pagina: Pagina) -> dict[str, str]:
    """Junta as palavras de cada rótulo (na ordem de leitura). Os pontos da tabela ficam em
    `ponto.nominal`, `ponto.encontrado`… com um valor por linha, separados por " | "."""
    por_campo: dict[str, list] = defaultdict(list)
    for palavra, (rotulo, _) in zip(pagina.palavras, prever(modelo, pagina), strict=True):
        if rotulo != OUTRO:
            por_campo[rotulo].append(palavra)
    resultado: dict[str, str] = {}
    for campo, palavras in por_campo.items():
        palavras.sort(key=lambda p: (round(p.centro[1], 2), p.caixa[0]))
        if campo.startswith("ponto."):
            linhas: list[list[str]] = []
            y_anterior = None
            for p in palavras:
                if y_anterior is None or abs(p.centro[1] - y_anterior) > 0.008:
                    linhas.append([])
                linhas[-1].append(p.texto)
                y_anterior = p.centro[1]
            resultado[campo] = " | ".join(" ".join(linha) for linha in linhas)
        else:
            resultado[campo] = " ".join(p.texto for p in palavras)
    return resultado


def salvar(modelo: Pipeline, caminho: Path | str) -> None:
    joblib.dump(modelo, caminho)


def abrir(caminho: Path | str) -> Pipeline:
    return joblib.load(caminho)
