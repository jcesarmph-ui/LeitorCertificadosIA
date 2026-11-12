"""Mede o aprendizado com o uso: quanto o modelo melhora a cada certificado real corrigido.

Método "deixa um de fora": para cada certificado real (gabarito = `certo` revisado), treina SEM
ele e testa NELE. Compara 4 situações — só fictícios, e fictícios + 1, 2 ou 3 outros reais
corrigidos. Os reais ficam em `dados/` (fora do Git); só os números vão para o README.

Medidas (no certificado deixado de fora):
- ESSENCIAIS: o que a conferência com o plano usa — código, faixa e pontos (nominal, encontrado,
  erro, incerteza). É a medida que importa;
- outros campos: fabricante, laboratório, técnico, datas…;
- falsos: palavras "outro" que o modelo marcou como campo (ruído).

Uso: python scripts/medir_aprendizado.py [--fictícios 60]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.aprendizado import modelo as modelo_mod  # noqa: E402
from leitor_certificados.aprendizado.correcoes import (  # noqa: E402
    carregar_pasta,
    treinar_com_correcoes,
)
from leitor_certificados.aprendizado.modelo import prever  # noqa: E402
from leitor_certificados.aprendizado.rotulos import OUTRO, rotular  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402

# As pistas de cada página não mudam entre os treinos: calcula uma vez só (muito mais rápido).
_original = modelo_mod.atributos_da_pagina
_cache: dict[int, list] = {}


def _pistas_em_cache(pagina):
    if id(pagina) not in _cache:
        _cache[id(pagina)] = _original(pagina)
    return _cache[id(pagina)]


modelo_mod.atributos_da_pagina = _pistas_em_cache


# O que importa para comparar com o plano: o código acha o plano; faixa e pontos (nominal, erro,
# incerteza) são comparados com a tolerância. Fabricante, laboratório, técnico etc. são secundários.
ESSENCIAIS = {"codigo", "faixa", "ponto.nominal", "ponto.encontrado", "ponto.erro",
              "ponto.incerteza"}


def medir(modelo, pagina, certos):
    """(essenciais certos, essenciais, outros campos certos, outros campos, falsos)."""
    previstos = [r for r, _ in prever(modelo, pagina)]
    e_ok = e = o_ok = o = falsos = 0
    for prev, certo in zip(previstos, certos, strict=True):
        if certo == OUTRO:
            falsos += prev != OUTRO
        elif certo in ESSENCIAIS:
            e += 1
            e_ok += prev == certo
        else:
            o += 1
            o_ok += prev == certo
    return e_ok, e, o_ok, o, falsos


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ficticios", type=int, default=60)
    n_fict = ap.parse_args().ficticios

    pasta = RAIZ / "dados" / "ficticios"
    paginas, rotulos = [], []
    for n in range(1, n_fict + 1):
        gab = json.loads(gerar_um(pasta, n).read_text(encoding="utf-8"))
        pag = ler_pdf(pasta / gab["digital"]["arquivo"])[0]
        paginas.append(pag)
        rotulos.append(rotular(pag, gab["digital"]["campos"]))

    arquivos = sorted((RAIZ / "dados" / "reais_marcacao").glob("*.palavras.json"))
    reais = carregar_pasta(RAIZ / "dados" / "reais_marcacao")
    nomes = [a.name[:14] for a in arquivos]
    print(f"{n_fict} fictícios; {len(reais)} reais corrigidos: {nomes}\n")

    por_k: dict[int, list[tuple[float, float, float]]] = {k: [] for k in range(len(reais))}
    for alvo in range(len(reais)):
        outros = [i for i in range(len(reais)) if i != alvo]
        print(f"{nomes[alvo]} (deixado de fora)")
        for k in range(len(outros) + 1):
            medidas = []
            for escolha in itertools.combinations(outros, k):
                modelo = treinar_com_correcoes(paginas, rotulos, [reais[i] for i in escolha])
                medidas.append(medir(modelo, *reais[alvo]))
            n = len(medidas)
            ess = sum(m[0] / m[1] for m in medidas) / n
            sec = sum(m[2] / m[3] for m in medidas) / n if medidas[0][3] else float("nan")
            fal = sum(m[4] for m in medidas) / n
            por_k[k].append((ess, sec, fal))
            print(f"   com {k} outro(s) real(is): ESSENCIAIS {100 * ess:5.1f} % | "
                  f"outros campos {100 * sec:5.1f} % | falsos {fal:5.1f}")
    print("\nMÉDIA nos certificados deixados de fora")
    for k, itens in por_k.items():
        n = len(itens)
        print(f"   com {k} real(is): ESSENCIAIS {100 * sum(i[0] for i in itens) / n:5.1f} % | "
              f"outros campos {100 * sum(i[1] for i in itens) / n:5.1f} % | "
              f"falsos {sum(i[2] for i in itens) / n:5.1f}")


if __name__ == "__main__":
    main()
