"""Mede a leitura (etapa 2) contra o gabarito: de cada 100 respostas, quantas foram lidas certas?

Gera um lote de certificados fictícios numa pasta temporária, lê cada um pelos dois caminhos
(digital = texto direto; escaneado = OCR) e compara o texto lido dentro de cada caixa do gabarito
com a resposta certa. A comparação ignora espaços ("41 %" = "41%").

Uso: python scripts/medir_leitura.py --quantidade 40
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

from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402


def _sem_espacos(texto: str) -> str:
    return "".join(texto.split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Mede o acerto da leitura contra o gabarito.")
    parser.add_argument("--quantidade", type=int, default=40)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    certos = {"digital": Counter(), "escaneado": Counter()}
    total = {"digital": Counter(), "escaneado": Counter()}
    tempo = {"digital": 0.0, "escaneado": 0.0}
    erros: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        for numero in range(1, args.quantidade + 1):
            gabarito = json.loads(gerar_um(pasta, numero).read_text(encoding="utf-8"))
            for versao, folga in (("digital", 0.0), ("escaneado", 0.004)):
                inicio = time.perf_counter()
                (pagina,) = ler_pdf(pasta / gabarito[versao]["arquivo"])
                tempo[versao] += time.perf_counter() - inicio
                for campo in gabarito[versao]["campos"]:
                    nome = campo["campo"]
                    total[versao][nome] += 1
                    lido = pagina.texto_na_caixa(campo["caixa"], folga)
                    if _sem_espacos(lido) == _sem_espacos(campo["texto"]):
                        certos[versao][nome] += 1
                    elif versao == "escaneado":
                        erros.append(f"{nome}: {campo['texto']!r} -> {lido!r}")

    for versao in ("digital", "escaneado"):
        t, c = sum(total[versao].values()), sum(certos[versao].values())
        print(f"\n{versao}: {c} de {t} respostas certas ({100 * c / t:.1f} %) — "
              f"{tempo[versao] / args.quantidade:.2f} s por certificado")
        for nome in sorted(total[versao]):
            if certos[versao][nome] != total[versao][nome]:
                print(f"   {nome}: {certos[versao][nome]} de {total[versao][nome]}")
    print(f"\nErros do OCR ({len(erros)}):")
    for erro in erros:
        print("  ", erro)


if __name__ == "__main__":
    main()
