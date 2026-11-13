"""Transforma o PDF digital num PDF "escaneado": só imagem, torta, com ruído e sem texto.

Por que: muitos certificados chegam escaneados. Neles não existe texto dentro do PDF — só uma
foto da folha —, e a leitura precisa de OCR (etapa 2). Para treinar e medir isso sem usar
certificados reais, imitamos o que um scanner faz:
- cinza e resolução de scanner (150 dpi na maioria das vezes, como o scanner real do autor;
  às vezes 200);
- folha um pouco **torta** (até 1,5°) e **deslocada**;
- **ruído** (sujeira do papel), leve **desfoque** e contraste diferente;
- compressão **JPEG**, que deixa "borrões" em volta das letras.
Como a folha gira, as caixas do gabarito também giram — calculamos onde cada uma foi parar.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter


def _girar_caixa(caixa: list[float], largura: int, altura: int, angulo: float,
                 dx: int, dy: int) -> list[float]:
    """Onde a caixa [esq, topo, dir, base] (fração da página) fica depois de girar e deslocar."""
    cx, cy = largura / 2, altura / 2
    cos, sen = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
    xs, ys = [], []
    for fx in (caixa[0], caixa[2]):
        for fy in (caixa[1], caixa[3]):
            x, y = fx * largura - cx, fy * altura - cy
            # Pillow gira no sentido anti-horário (com o eixo y para baixo)
            xs.append(cx + x * cos + y * sen + dx)
            ys.append(cy - x * sen + y * cos + dy)
    return [
        round(min(xs) / largura, 4), round(min(ys) / altura, 4),
        round(max(xs) / largura, 4), round(max(ys) / altura, 4),
    ]


def escanear(pdf_digital: Path, destino: Path, rng: random.Random,
             campos: list[dict]) -> tuple[list[dict], dict]:
    """Grava o PDF escaneado em `destino`; devolve os campos com as caixas novas e o que foi
    feito na imagem (para o gabarito)."""
    dpi = rng.choice((150, 150, 150, 200))
    documento = pdfium.PdfDocument(str(pdf_digital))
    try:
        imagem = documento[0].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
    finally:
        documento.close()

    largura, altura = imagem.size
    angulo = round(rng.uniform(-1.5, 1.5), 2)
    dx, dy = rng.randint(-15, 15), rng.randint(-15, 15)
    imagem = imagem.rotate(angulo, resample=Image.Resampling.BICUBIC, fillcolor=255,
                           translate=(dx, dy))

    # Ruído com a mesma semente (randbytes), para o arquivo sair igual toda vez
    ruido = Image.frombytes("L", imagem.size, rng.randbytes(largura * altura))
    imagem = Image.blend(imagem, ruido, rng.uniform(0.04, 0.14))
    imagem = imagem.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.1)))
    imagem = ImageEnhance.Contrast(imagem).enhance(rng.uniform(0.8, 1.2))
    imagem = ImageEnhance.Brightness(imagem).enhance(rng.uniform(0.95, 1.05))

    qualidade = rng.randint(35, 80)
    memoria = io.BytesIO()
    imagem.save(memoria, "JPEG", quality=qualidade)
    memoria.seek(0)
    Image.open(memoria).save(destino, "PDF", resolution=dpi)

    novos = [
        {**c, "caixa": _girar_caixa(c["caixa"], largura, altura, angulo, dx, dy)} for c in campos
    ]
    ajustes = {"dpi": dpi, "angulo_graus": angulo, "deslocamento_px": [dx, dy],
               "qualidade_jpeg": qualidade}
    return novos, ajustes
