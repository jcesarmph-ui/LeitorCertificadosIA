"""O quadradinho de cor de cada rótulo, usado na lista de rótulos do modo Corrigir.

(A legenda embaixo da folha saiu a pedido do usuário em 2026-11-12: com todas as caixas da mesma
cor, ela não dizia nada; o tipo de cada valor aparece na dica do mouse.)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from .paletas import cor_rgb, paleta


def amostra(rotulo: str | None, tamanho: int = 14, tracejada: bool = False) -> QPixmap:
    """Um quadradinho com a cor do rótulo (contorno + cor dentro, como na folha)."""
    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    if rotulo is None or rotulo == "outro":
        cor = QColor(150, 150, 150)
    else:
        cor = QColor(*cor_rgb(rotulo))
    dentro = QColor(cor)
    dentro.setAlpha(0 if tracejada else (70 if paleta().preencher else 25))
    pintor.fillRect(1, 1, tamanho - 2, tamanho - 2, dentro)
    pintor.setPen(QPen(cor, 2, Qt.PenStyle.DashLine if tracejada else Qt.PenStyle.SolidLine))
    pintor.drawRect(1, 1, tamanho - 3, tamanho - 3)
    pintor.end()
    return pixmap


def icone_do_rotulo(rotulo: str) -> QIcon:
    return QIcon(amostra(rotulo, 16))
