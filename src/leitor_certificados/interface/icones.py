"""Ícones Material Symbols (Outlined) guardados em `icones/`, pintados na cor do tema.

O SVG fica preto no arquivo; aqui trocamos o preenchimento pela cor pedida antes de desenhar.
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PASTA_ICONES = Path(__file__).with_name("icones")


def icone(nome: str, cor: str, tamanho: int = 48) -> QIcon:
    """Lê `icones/<nome>.svg` e devolve o ícone pintado na `cor` (ex.: "#1b2533")."""
    svg = (PASTA_ICONES / f"{nome}.svg").read_text(encoding="utf-8")
    svg = svg.replace("<path ", f'<path fill="{cor}" ', 1)
    desenho = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    imagem = QPixmap(tamanho, tamanho)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    desenho.render(pintor, QRectF(0, 0, tamanho, tamanho))
    pintor.end()
    return QIcon(imagem)
