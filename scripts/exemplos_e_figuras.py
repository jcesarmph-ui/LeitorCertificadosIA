"""Monta a pasta `exemplos/` (um certificado fictício de cada laboratório) e as figuras do README.

Figuras em `docs/figuras/`:
- `laboratorios.png`        — o topo de um certificado de cada laboratório inventado, lado a lado;
- `digital_x_escaneado.png` — o mesmo certificado nas duas versões;
- `gabarito.png`            — o escaneado com as caixas do gabarito pintadas por tipo de informação.
Tudo fictício: sai do próprio gerador do projeto.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.ficticio.laboratorios import LABORATORIOS  # noqa: E402

CORES = {
    "laboratorio": ((123, 31, 162), "Laboratório"),
    "numero_certificado": ((198, 40, 40), "Nº do certificado"),
    "data_calibracao": ((21, 101, 192), "Data da calibração"),
    "codigo": ((239, 108, 0), "Código do instrumento"),
    "ponto": ((46, 125, 50), "Pontos (nominal, encontrado, erro, U, k)"),
}
OUTROS = ((120, 120, 120), "Outras informações anotadas")


def _imagem(pdf: Path, escala: float = 1.6) -> Image.Image:
    documento = pdfium.PdfDocument(str(pdf))
    try:
        return documento[0].render(scale=escala).to_pil().convert("RGB")
    finally:
        documento.close()


def _fonte(tamanho: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", tamanho)
    except OSError:
        return ImageFont.load_default()


def _topo(img: Image.Image, fracao: float = 0.62) -> Image.Image:
    return img.crop((0, 0, img.width, int(img.height * fracao)))


def _lado_a_lado(imagens: list[Image.Image], espaco: int = 24) -> Image.Image:
    altura = max(i.height for i in imagens)
    largura = sum(i.width for i in imagens) + espaco * (len(imagens) + 1)
    tela = Image.new("RGB", (largura, altura + 2 * espaco), (235, 235, 235))
    x = espaco
    for i in imagens:
        tela.paste(i, (x, espaco))
        x += i.width + espaco
    return tela


def main() -> None:
    exemplos = RAIZ / "exemplos"
    figuras = RAIZ / "docs" / "figuras"
    exemplos.mkdir(exist_ok=True)
    figuras.mkdir(parents=True, exist_ok=True)

    escolhidos: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp)
        numero = 0
        while len(escolhidos) < len(LABORATORIOS):  # o primeiro de cada laboratório
            numero += 1
            gabarito = json.loads(gerar_um(pasta, numero).read_text(encoding="utf-8"))
            chave = gabarito["certificado"]["laboratorio"]
            if chave not in escolhidos:
                escolhidos[chave] = gabarito
                for arquivo in (gabarito["digital"]["arquivo"], gabarito["escaneado"]["arquivo"],
                                f"{gabarito['certificado']['id']}.json"):
                    shutil.copy2(pasta / arquivo, exemplos / arquivo)

        ordem = [escolhidos[c] for c in LABORATORIOS]
        topos = [_topo(_imagem(pasta / g["digital"]["arquivo"], 0.9)) for g in ordem]
        _lado_a_lado(topos).save(figuras / "laboratorios.png", optimize=True)

        g = max(ordem, key=lambda g: abs(g["escaneado"]["angulo_graus"]))
        digital = _topo(_imagem(pasta / g["digital"]["arquivo"]))
        escaneado = _topo(_imagem(pasta / g["escaneado"]["arquivo"]))
        _lado_a_lado([digital, escaneado]).save(figuras / "digital_x_escaneado.png", optimize=True)

        img = _topo(_imagem(pasta / g["escaneado"]["arquivo"], 1.6), 1.0)
        desenho = ImageDraw.Draw(img)
        for campo in g["escaneado"]["campos"]:
            chave = "ponto" if campo["campo"].startswith("ponto.") else campo["campo"]
            cor, _ = CORES.get(chave, OUTROS)
            esq, topo, dir_, base = campo["caixa"]
            desenho.rectangle((esq * img.width - 2, topo * img.height - 2,
                               dir_ * img.width + 2, base * img.height + 2), outline=cor, width=3)
        img = _topo(img, 0.62)
        legenda = Image.new("RGB", (img.width, 40 + 30 * (len(CORES) + 1)), "white")
        escrita = ImageDraw.Draw(legenda)
        for n, (cor, nome) in enumerate([*CORES.values(), OUTROS]):
            y = 20 + 30 * n
            escrita.rectangle((30, y, 60, y + 20), outline=cor, width=3)
            escrita.text((75, y), nome, fill=(30, 30, 30), font=_fonte(20))
        final = Image.new("RGB", (img.width, img.height + legenda.height), "white")
        final.paste(img, (0, 0))
        final.paste(legenda, (0, img.height))
        final.save(figuras / "gabarito.png", optimize=True)
    print("exemplos:", sorted(p.name for p in exemplos.iterdir()))
    print("figuras:", sorted(p.name for p in figuras.iterdir()))


if __name__ == "__main__":
    main()
