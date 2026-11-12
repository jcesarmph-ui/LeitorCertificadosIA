"""Foto de revisão: mostra o que a pessoa (ou a proposta) mudou em relação ao palpite do modelo.

Para cada `dados/reais_marcacao/<nome>.palavras.json` grava `<nome>.revisao.png`: as palavras são
pintadas pelo rótulo `certo`; as que mudaram ganham contorno grosso e "i: antes → depois".
Uso: python scripts/foto_revisao.py [começo-do-nome]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
from pre_rotular_reais import COR_PADRAO, CORES, PASTA_REAIS, SAIDA  # noqa: E402

CORES_EXTRA = {"ponto.erro_maximo": (160, 100, 40), "ponto.criterio": (20, 100, 100)}


def main() -> None:
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    fonte = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
    for arq in sorted(SAIDA.glob(f"{filtro}*.palavras.json")):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        pdf = PASTA_REAIS / (arq.name.removesuffix(".palavras.json") + ".pdf")
        doc = pdfium.PdfDocument(str(pdf))
        folha = doc[0].render(scale=2.2).to_pil().convert("RGB")
        if dados.get("rotacao") == 180:  # as caixas estão no quadro da folha já virada em pé
            folha = folha.rotate(180)
        doc.close()
        d = ImageDraw.Draw(folha, "RGBA")
        L, A = folha.size
        for it in dados["palavras"]:
            mudou = it["certo"] != it["rotulo"]
            if it["certo"] == "outro" and not mudou:
                continue
            e, t, r, b = it["caixa"]
            cor = {**CORES, **CORES_EXTRA}.get(it["certo"], COR_PADRAO)
            if it["certo"] == "outro":
                cor = (0, 0, 0)
            d.rectangle([e * L, t * A, r * L, b * A], outline=cor + (255,),
                        width=4 if mudou else 1, fill=cor + (50,) if not mudou else cor + (90,))
            if mudou:
                d.text((e * L, t * A - 16), f"{it['i']}: {it['rotulo'][:10]}→{it['certo'][:10]}",
                       font=fonte, fill=(0, 0, 0, 255))
        saida = SAIDA / (arq.name.removesuffix(".palavras.json") + ".revisao.png")
        try:
            folha.save(saida)
            print(saida.name)
        except OSError:  # foto aberta em outro programa
            print(f"AVISO: feche {saida.name} e rode de novo para atualizá-la.")


if __name__ == "__main__":
    main()
