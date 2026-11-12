"""Aprender com o uso: certificados reais corrigidos à mão viram treino.

O fluxo (ADR 0007):
1. `scripts/pre_rotular_reais.py` lê o certificado e grava `<nome>.palavras.json` com o palpite do
   modelo (`rotulo`) e um campo `certo`, que começa igual ao palpite;
2. a pessoa corrige `certo` onde o modelo errou (`"i"` é o número da palavra, o mesmo da foto);
3. `treinar_com_correcoes` junta os fictícios com esses reais corrigidos, dando mais peso aos reais.

Os JSON reais ficam em `dados/` (fora do Git, ADR 0002). Aqui só há o código.
"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.pipeline import Pipeline

from ..leitura import Pagina, Palavra
from .modelo import treinar_com_rotulos

PESO_REAL = 5.0  # um certificado real corrigido conta como 5 fictícios


def carregar_marcacao(arquivo: Path | str) -> tuple[Pagina, list[str]]:
    """Lê um `.palavras.json` e devolve a página e o rótulo `certo` de cada palavra."""
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    palavras = [Palavra(i["texto"], tuple(i["caixa"]), i["confianca"]) for i in dados["palavras"]]
    pagina = Pagina(dados["origem"], palavras, dados.get("rotacao", 0))
    return pagina, [i["certo"] for i in dados["palavras"]]


def carregar_pasta(pasta: Path | str) -> list[tuple[Pagina, list[str]]]:
    return [carregar_marcacao(a) for a in sorted(Path(pasta).glob("*.palavras.json"))]


def contar_correcoes(arquivo: Path | str) -> int:
    """Quantas palavras a pessoa mudou em relação ao palpite do modelo."""
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    return sum(i["certo"] != i["rotulo"] for i in dados["palavras"])


def treinar_com_correcoes(
    paginas: list[Pagina], rotulos: list[list[str]],
    reais: list[tuple[Pagina, list[str]]], peso_real: float = PESO_REAL,
) -> Pipeline:
    """Treina com os fictícios (`paginas` + `rotulos`) e os reais corrigidos (`reais`)."""
    todas = paginas + [p for p, _ in reais]
    todos_rotulos = rotulos + [r for _, r in reais]
    pesos = [1.0] * len(paginas) + [peso_real] * len(reais)
    return treinar_com_rotulos(todas, todos_rotulos, pesos)
