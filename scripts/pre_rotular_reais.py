"""Pré-marca os certificados REAIS com o modelo e desenha a folha para conferir.

Roda só neste PC: lê de `dados/certificados_reais/` e grava em `dados/reais_marcacao/` (a pasta
`dados/` é ignorada pelo Git — nada real vai para o GitHub).

Para cada PDF grava:
- `<nome>.palavras.json` — cada palavra lida, a caixa, a confiança do OCR e o rótulo que o modelo
  chutou (`rotulo`); o campo `certo` começa igual ao chute e é onde se corrige à mão;
- `<nome>.png` — a folha com as caixas coloridas por rótulo e o número de cada palavra, para
  conferir de olho.

Uso: python scripts/pre_rotular_reais.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.aprendizado.modelo import prever, treinar  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402

PASTA_REAIS = RAIZ / "dados" / "certificados_reais"
SAIDA = RAIZ / "dados" / "reais_marcacao"
CORES = {
    "ponto.nominal": (0, 120, 215), "ponto.encontrado": (0, 160, 90), "ponto.erro": (230, 120, 0),
    "ponto.incerteza": (200, 30, 30), "ponto.k": (150, 60, 200), "codigo": (0, 150, 150),
    "tipo": (120, 120, 0), "laboratorio": (90, 90, 90),
}
COR_PADRAO = (190, 0, 120)


def treinar_com_ficticios(quantidade: int = 150):
    pasta = RAIZ / "dados" / "ficticios"
    paginas, campos = [], []
    for n in range(1, quantidade + 1):
        gab = json.loads(gerar_um(pasta, n).read_text(encoding="utf-8"))
        paginas.append(ler_pdf(pasta / gab["digital"]["arquivo"])[0])
        campos.append(gab["digital"]["campos"])
    return treinar(paginas, campos)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    SAIDA.mkdir(parents=True, exist_ok=True)
    modelo = treinar_com_ficticios()
    fonte = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
    for pdf in sorted(PASTA_REAIS.glob("*.pdf")):
        (pagina,) = ler_pdf(pdf)[:1]
        previsoes = prever(modelo, pagina)
        itens = [
            {"i": i, "texto": p.texto, "caixa": list(p.caixa), "confianca": p.confianca,
             "rotulo": r, "certeza": round(c, 3), "certo": r}
            for i, (p, (r, c)) in enumerate(zip(pagina.palavras, previsoes, strict=True))
        ]
        (SAIDA / f"{pdf.stem}.palavras.json").write_text(
            json.dumps({"origem": pagina.origem, "palavras": itens}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        doc = pdfium.PdfDocument(str(pdf))
        folha = doc[0].render(scale=2.2).to_pil().convert("RGB")
        doc.close()
        d = ImageDraw.Draw(folha, "RGBA")
        L, A = folha.size
        for it in itens:
            if it["rotulo"] == "outro":
                continue
            e, t, r, b = it["caixa"]
            cor = CORES.get(it["rotulo"], COR_PADRAO)
            d.rectangle([e * L, t * A, r * L, b * A], outline=cor + (255,), width=2,
                        fill=cor + (40,))
            d.text((e * L, t * A - 17), f"{it['i']}", font=fonte, fill=cor + (255,))
        folha.save(SAIDA / f"{pdf.stem}.png")
        marcadas = sum(it["rotulo"] != "outro" for it in itens)
        print(f"{pdf.name[:18]}: {pagina.origem}, {len(itens)} palavras, {marcadas} marcadas")


if __name__ == "__main__":
    main()
