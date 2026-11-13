"""Figura do README da etapa 2: o que o OCR leu num certificado escaneado (fictício).

`docs/figuras/leitura_ocr.png` — cada palavra lida ganha um contorno com a cor da confiança do
OCR (verde = certeza alta, amarelo = dúvida, vermelho = pouca certeza) e, embaixo, o texto lido.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.leitura.ler import ler_pdf  # noqa: E402

VERDE, AMARELO, VERMELHO = (46, 125, 50), (245, 160, 0), (198, 40, 40)
LEGENDA = [
    (VERDE, "Certeza alta (95 % ou mais)"),
    (AMARELO, "Dúvida (de 80 % a 95 %)"),
    (VERMELHO, "Pouca certeza (menos de 80 %)"),
]


def _cor(confianca: float) -> tuple[int, int, int]:
    return VERDE if confianca >= 0.95 else AMARELO if confianca >= 0.80 else VERMELHO


def _fonte(tamanho: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", tamanho)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    # O exemplo com a menor confiança em alguma palavra: mostra as três cores
    candidatos = []
    for gabarito in sorted((RAIZ / "exemplos").glob("cert_*.json")):
        arquivo = json.loads(gabarito.read_text(encoding="utf-8"))["escaneado"]["arquivo"]
        (pagina,) = ler_pdf(RAIZ / "exemplos" / arquivo)
        candidatos.append((min(p.confianca for p in pagina.palavras), arquivo, pagina))
    _, arquivo, pagina = min(candidatos, key=lambda c: c[0])

    documento = pdfium.PdfDocument(str(RAIZ / "exemplos" / arquivo))
    try:
        img = documento[0].render(scale=2.0).to_pil().convert("RGB")
    finally:
        documento.close()
    desenho = ImageDraw.Draw(img)
    fonte = _fonte(13)
    for p in pagina.palavras:
        esq, topo, dir_, base = p.caixa
        cor = _cor(p.confianca)
        desenho.rectangle((esq * img.width, topo * img.height, dir_ * img.width,
                           base * img.height), outline=cor, width=2)
        desenho.text((esq * img.width, base * img.height + 1), p.texto, fill=cor, font=fonte)
    img = img.crop((0, 0, img.width, int(img.height * 0.66)))

    legenda = Image.new("RGB", (img.width, 30 + 34 * len(LEGENDA)), "white")
    escrita = ImageDraw.Draw(legenda)
    for n, (cor, nome) in enumerate(LEGENDA):
        y = 18 + 34 * n
        escrita.rectangle((30, y, 60, y + 22), outline=cor, width=3)
        escrita.text((75, y), nome, fill=(30, 30, 30), font=_fonte(22))
    final = Image.new("RGB", (img.width, img.height + legenda.height), "white")
    final.paste(img, (0, 0))
    final.paste(legenda, (0, img.height))
    destino = RAIZ / "docs" / "figuras" / "leitura_ocr.png"
    final.save(destino, optimize=True)
    print(destino, arquivo, len(pagina.palavras), "palavras")


if __name__ == "__main__":
    main()
