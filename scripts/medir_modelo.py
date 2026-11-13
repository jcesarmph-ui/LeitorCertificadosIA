"""Mede o machine learning (etapa 3): o modelo acha o que cada palavra é em certificados novos?

Três provas, da mais fácil para a mais difícil:
1. **Certificados novos** do mesmo mundo: treina com 80 % dos fictícios e testa nos 20 % restantes.
2. **Laboratório novo**: treina com 4 laboratórios e testa no quinto (que o modelo nunca viu).
3. **Escaneado**: treina no digital e testa nas palavras lidas por OCR (só nos certificados de
   teste, porque o OCR demora uns 5 s por folha).

Uso: python scripts/medir_modelo.py --quantidade 150 --escaneados 30
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.aprendizado.modelo import prever, treinar  # noqa: E402
from leitor_certificados.aprendizado.rotulos import OUTRO, rotular  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402


def carregar(pasta: Path, quantidade: int, escaneados: int):
    dados = []
    for n in range(1, quantidade + 1):
        gab = json.loads(gerar_um(pasta, n).read_text(encoding="utf-8"))
        (pag,) = ler_pdf(pasta / gab["digital"]["arquivo"])
        item = {"lab": gab["certificado"]["laboratorio"], "digital": pag,
                "campos": gab["digital"]["campos"], "escaneado": None}
        if n > quantidade - escaneados:  # OCR demora: só nos últimos (o conjunto de teste)
            (esc,) = ler_pdf(pasta / gab["escaneado"]["arquivo"])
            item["escaneado"] = (esc, gab["escaneado"]["campos"])
        dados.append(item)
    return dados


def avaliar(modelo, paginas_e_campos, folga):
    palavras = certas = 0
    campos_total = campos_certos = 0
    falsos = 0
    erros = Counter()
    for pagina, campos in paginas_e_campos:
        verdade = rotular(pagina, campos, folga)
        palpites = [r for r, _ in prever(modelo, pagina)]
        for v, p in zip(verdade, palpites, strict=True):
            palavras += 1
            certas += v == p
            if v != p:
                erros[(v, p)] += 1
            falsos += v == OUTRO and p != OUTRO
        for campo in campos:
            esq, topo, dir_, base = campo["caixa"]
            dentro = [i for i, w in enumerate(pagina.palavras)
                      if esq - folga <= w.centro[0] <= dir_ + folga
                      and topo - folga <= w.centro[1] <= base + folga]
            if dentro:
                campos_total += 1
                campos_certos += all(palpites[i] == campo["campo"] for i in dentro)
    return palavras, certas, campos_total, campos_certos, falsos, erros


def relatorio(titulo, resultado):
    palavras, certas, ct, cc, falsos, erros = resultado
    pc = 100 * certas / palavras
    print(f"\n{titulo}\n   palavras certas: {certas} de {palavras} ({pc:.1f} %)"
          f"\n   campos inteiros certos: {cc} de {ct} ({100 * cc / ct:.1f} %)"
          f"\n   falsos alarmes (palavra comum tratada como campo): {falsos}")
    for (v, p), q in erros.most_common(6):
        print(f"      {q}x  era {v!r}, o modelo disse {p!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantidade", type=int, default=150)
    parser.add_argument("--escaneados", type=int, default=30)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        inicio = time.perf_counter()
        dados = carregar(Path(tmp), args.quantidade, args.escaneados)
        print(f"{len(dados)} certificados lidos em {time.perf_counter() - inicio:.0f} s")

        corte = int(len(dados) * 0.8)
        treino, teste = dados[:corte], dados[corte:]
        t = time.perf_counter()
        modelo = treinar([d["digital"] for d in treino], [d["campos"] for d in treino])
        print(f"treino com {len(treino)} certificados: {time.perf_counter() - t:.1f} s")
        relatorio(f"1) Certificados novos (digital, {len(teste)} no teste)",
                  avaliar(modelo, [(d["digital"], d["campos"]) for d in teste], 0.0))

        for lab in sorted({d["lab"] for d in dados}):
            tr = [d for d in dados if d["lab"] != lab]
            te = [d for d in dados if d["lab"] == lab]
            m = treinar([d["digital"] for d in tr], [d["campos"] for d in tr])
            relatorio(f"2) Laboratório novo: {lab} ({len(te)} certificados, o modelo nunca viu)",
                      avaliar(m, [(d["digital"], d["campos"]) for d in te], 0.0))

        alvo = [d["escaneado"] for d in teste if d["escaneado"]]
        relatorio(f"3) Escaneado por OCR ({len(alvo)} certificados; treino só com digital)",
                  avaliar(modelo, alvo, 0.004))


if __name__ == "__main__":
    main()
