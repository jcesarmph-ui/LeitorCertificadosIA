"""Corrige o palpite do modelo num certificado real (aprendizado com o uso).

Muda o campo `certo` das palavras indicadas em `dados/reais_marcacao/<nome>.palavras.json`. Os
números são os que aparecem em cima de cada caixa na foto. Aceita números soltos e faixas.

Exemplos (da pasta do projeto):
  python scripts/corrigir_reais.py scan11 --palavras 139,144,150-160 --rotulo ponto.nominal
  python scripts/corrigir_reais.py scan11 --palavras 18 --rotulo outro
  python scripts/corrigir_reais.py scan11 --listar          # mostra o que já foi corrigido

O `<nome>` pode ser só o começo do nome do arquivo. Rótulos válidos: ver --rotulos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "dados" / "reais_marcacao"
ROTULOS = ["outro", "ponto.nominal", "ponto.encontrado", "ponto.erro", "ponto.incerteza",
           "ponto.k", "codigo", "tipo", "laboratorio"]


def numeros(texto: str) -> set[int]:
    achados: set[int] = set()
    for parte in texto.split(","):
        parte = parte.strip()
        if "-" in parte:
            a, b = parte.split("-")
            achados |= set(range(int(a), int(b) + 1))
        elif parte:
            achados.add(int(parte))
    return achados


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("nome", nargs="?", help="começo do nome do arquivo")
    ap.add_argument("--palavras", help="números e faixas, ex.: 139,144,150-160")
    ap.add_argument("--rotulo", help="o rótulo certo")
    ap.add_argument("--listar", action="store_true", help="mostra as palavras já corrigidas")
    ap.add_argument("--rotulos", action="store_true", help="lista os rótulos conhecidos")
    a = ap.parse_args()
    if a.rotulos:
        print("\n".join(ROTULOS))
        return
    arquivos = sorted(SAIDA.glob(f"{a.nome or ''}*.palavras.json"))
    if len(arquivos) != 1:
        sys.exit(f"Preciso de exatamente 1 arquivo; achei {len(arquivos)}: "
                 f"{[x.name for x in arquivos]}")
    arquivo = arquivos[0]
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if a.listar:
        for it in dados["palavras"]:
            if it["certo"] != it["rotulo"]:
                print(f"{it['i']:>4}  {it['texto']:<20} {it['rotulo']} -> {it['certo']}")
        return
    if not (a.palavras and a.rotulo):
        sys.exit("Faltou --palavras e/ou --rotulo.")
    alvo = numeros(a.palavras)
    if a.rotulo not in ROTULOS:
        print(f"Aviso: '{a.rotulo}' não está na lista conhecida (um rótulo novo é permitido).")
    existentes = {it["i"] for it in dados["palavras"]}
    if alvo - existentes:
        sys.exit(f"Números que não existem: {sorted(alvo - existentes)}")
    for it in dados["palavras"]:
        if it["i"] in alvo:
            it["certo"] = a.rotulo
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(alvo)} palavra(s) de {arquivo.name[:20]} agora são '{a.rotulo}'.")


if __name__ == "__main__":
    main()
