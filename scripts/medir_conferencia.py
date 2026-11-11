"""Mede a etapa 4 de ponta a ponta: o parecer (aprovado/reprovado) sai certo?

Gera certificados fictícios e, para cada um, um plano inventado com a resposta certa calculada
do gabarito. Depois: PDF → leitura → modelo → plano → parecer, e compara com a resposta certa.

Provas:
1. certificados novos, digital;  2. os mesmos, escaneados (OCR);
3. laboratório que o modelo nunca viu (digital).

Uso: python scripts/medir_conferencia.py --quantidade 150 --escaneados 30
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.aprendizado.modelo import treinar  # noqa: E402
from leitor_certificados.conferencia.avaliacao import Resultado  # noqa: E402
from leitor_certificados.conferencia.conferir import conferir  # noqa: E402
from leitor_certificados.conferencia.extracao import montar_certificado  # noqa: E402
from leitor_certificados.conferencia.plano import PlanosDQ05  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.ficticio.plano import criar_banco_de_planos  # noqa: E402
from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402


def medir(titulo, modelo, itens, planos, certo):
    pareceres = pontos_total = pontos_certos = 0
    erros = []
    for pagina, gab in itens:
        cert = gab["certificado"]
        conf = conferir(montar_certificado(modelo, pagina), planos)
        pareceres += conf.resultado == certo[cert["id"]]
        if conf.resultado != certo[cert["id"]]:
            erros.append(f"{cert['id']} ({cert['laboratorio']}): certo {certo[cert['id']].value}, "
                         f"deu {conf.resultado.value}; avisos: {conf.avisos[:2]}")
        # pontos: o número de pontos lidos e avaliados bate com o certificado?
        pontos_total += len(cert["pontos"])
        pontos_certos += sum(
            1 for p in conf.pontos if p.avaliacao.resultado != Resultado.NAO_AVALIADO
        )
    print(f"\n{titulo}\n   pareceres certos: {pareceres} de {len(itens)} "
          f"({100 * pareceres / len(itens):.1f} %)"
          f"\n   pontos da tabela lidos e avaliados: {pontos_certos} de {pontos_total} "
          f"({100 * pontos_certos / pontos_total:.1f} %)")
    for e in erros[:6]:
        print("     -", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantidade", type=int, default=150)
    parser.add_argument("--escaneados", type=int, default=30)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        gabs, digitais, escaneados = [], [], {}
        for n in range(1, args.quantidade + 1):
            g = json.loads(gerar_um(pasta, n).read_text(encoding="utf-8"))
            gabs.append(g)
            digitais.append(ler_pdf(pasta / g["digital"]["arquivo"])[0])
            if n > args.quantidade - args.escaneados:
                escaneados[n - 1] = ler_pdf(pasta / g["escaneado"]["arquivo"])[0]
        banco = pasta / "planos_inventados.db"
        certo = criar_banco_de_planos(banco, [g["certificado"] for g in gabs])
        planos = PlanosDQ05(banco)
        reprovados = sum(r == Resultado.REPROVADO for r in certo.values())
        print(f"{len(gabs)} certificados; {reprovados} reprovados e "
              f"{len(certo) - reprovados} aprovados no plano inventado")

        corte = int(len(gabs) * 0.8)
        modelo = treinar(digitais[:corte], [g["digital"]["campos"] for g in gabs[:corte]])
        medir(f"1) Digital, certificados novos ({len(gabs) - corte})", modelo,
              list(zip(digitais[corte:], gabs[corte:], strict=True)), planos, certo)
        medir(f"2) Escaneado por OCR ({len(escaneados)})", modelo,
              [(escaneados[i], gabs[i]) for i in sorted(escaneados) if i >= corte], planos, certo)
        for lab in sorted({g["certificado"]["laboratorio"] for g in gabs}):
            tr = [i for i, g in enumerate(gabs) if g["certificado"]["laboratorio"] != lab]
            te = [i for i, g in enumerate(gabs) if g["certificado"]["laboratorio"] == lab]
            m = treinar([digitais[i] for i in tr], [gabs[i]["digital"]["campos"] for i in tr])
            medir(f"3) Laboratório novo: {lab} ({len(te)}, digital)", m,
                  [(digitais[i], gabs[i]) for i in te], planos, certo)
        planos.fechar()


if __name__ == "__main__":
    main()
