"""Mede o aprendizado com o uso: quanto o modelo melhora a cada certificado real corrigido.

Método "deixa um de fora": para cada certificado real (gabarito = `certo` revisado), treina SEM
ele e testa NELE. Compara 4 situações — só fictícios, e fictícios + 1, 2 ou 3 outros reais
corrigidos. Os reais ficam em `dados/` (fora do Git); só os números vão para o README.

Medidas (no certificado deixado de fora):
- ESSENCIAIS: o que a conferência com o plano usa — código, faixa e pontos (nominal, encontrado,
  erro, incerteza). É a medida que importa;
- PADRÕES (etapa 8): código e validade de cada padrão e a data da calibração — o que a
  conferência da validade dos padrões usa;
- outros campos: fabricante, laboratório, técnico, data de emissão…;
- falsos: palavras "outro" que o modelo marcou como campo (ruído).

Com muitos reais, testar todas as combinações fica lento (9 reais = 2.304 treinos): `--maximo 6`
sorteia no máximo 6 combinações por quantidade (sempre as mesmas, semente fixa) e `--quantidades
0,1,2,4,8` mede só essas quantidades de reais no treino.

Uso: python scripts/medir_aprendizado.py [--ficticios 60] [--maximo 6] [--quantidades 0,1,2,4,8]
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
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
# Colunas que só alguns laboratórios trazem (ADR 0009): medidas à parte.
EXTRAS = {"ponto.erro_maximo", "ponto.criterio"}
# Validade dos padrões (etapa 8, ADR 0010): medida à parte.
PADROES = {"padrao.codigo", "padrao.validade", "data_calibracao"}


def medir(modelo, pagina, certos):
    """(essenciais certos, essenciais, outros certos, outros, falsos, extras certos, extras,
    padrões certos, padrões)."""
    previstos = [r for r, _ in prever(modelo, pagina)]
    e_ok = e = o_ok = o = falsos = x_ok = x = p_ok = p = 0
    for prev, certo in zip(previstos, certos, strict=True):
        if certo == OUTRO:
            falsos += prev != OUTRO
        elif certo in PADROES:
            p += 1
            p_ok += prev == certo
        elif certo in EXTRAS:
            x += 1
            x_ok += prev == certo
        elif certo in ESSENCIAIS:
            e += 1
            e_ok += prev == certo
        else:
            o += 1
            o_ok += prev == certo
    return e_ok, e, o_ok, o, falsos, x_ok, x, p_ok, p


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ficticios", type=int, default=60)
    ap.add_argument("--maximo", type=int, default=0, help="combinações por quantidade (0 = todas)")
    ap.add_argument("--quantidades", default="", help="ex.: 0,1,2,4,8 (vazio = todas)")
    args = ap.parse_args()
    n_fict = args.ficticios
    sorteio = random.Random(2026)

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

    quantidades = ([int(q) for q in args.quantidades.split(",")] if args.quantidades
                   else list(range(len(reais))))
    por_k: dict[int, list[tuple[float, float, float]]] = {k: [] for k in quantidades}
    for alvo in range(len(reais)):
        outros = [i for i in range(len(reais)) if i != alvo]
        print(f"{nomes[alvo]} (deixado de fora)")
        for k in quantidades:
            medidas = []
            escolhas = list(itertools.combinations(outros, k))
            if args.maximo and len(escolhas) > args.maximo:
                escolhas = sorteio.sample(escolhas, args.maximo)
            for escolha in escolhas:
                modelo = treinar_com_correcoes(paginas, rotulos, [reais[i] for i in escolha])
                medidas.append(medir(modelo, *reais[alvo]))
            n = len(medidas)
            ess = sum(m[0] / m[1] for m in medidas) / n
            sec = sum(m[2] / m[3] for m in medidas) / n if medidas[0][3] else float("nan")
            fal = sum(m[4] for m in medidas) / n
            pad = sum(m[7] / m[8] for m in medidas) / n if medidas[0][8] else None
            por_k[k].append((ess, sec, fal, pad))
            extras = (f" | erro máx./critério {100 * sum(m[5] / m[6] for m in medidas) / n:5.1f} %"
                      if medidas[0][6] else "")
            padroes = f" | PADRÕES {100 * pad:5.1f} %" if pad is not None else ""
            print(f"   com {k} outro(s) real(is): ESSENCIAIS {100 * ess:5.1f} % | "
                  f"outros campos {100 * sec:5.1f} % | falsos {fal:5.1f}{padroes}{extras}")
    print("\nMÉDIA nos certificados deixados de fora")
    for k, itens in por_k.items():
        n = len(itens)
        com_padroes = [i[3] for i in itens if i[3] is not None]
        padroes = (f" | PADRÕES {100 * sum(com_padroes) / len(com_padroes):5.1f} %"
                   if com_padroes else "")
        print(f"   com {k} real(is): ESSENCIAIS {100 * sum(i[0] for i in itens) / n:5.1f} % | "
              f"outros campos {100 * sum(i[1] for i in itens) / n:5.1f} % | "
              f"falsos {sum(i[2] for i in itens) / n:5.1f}{padroes}")


if __name__ == "__main__":
    main()
