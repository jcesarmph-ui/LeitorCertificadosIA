"""Botão liga/desliga (pedido do usuário, 2026-11-17): mais fácil de entender que um botão que
fica afundado. Desligado: bolinha à esquerda, trilho cinza. Ligado: bolinha à direita e trilho
verde. O texto fica ao lado."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from .estilo import VERDE, cor

LARGURA_TRILHO, ALTURA_TRILHO = 46, 24


class Interruptor(QAbstractButton):
    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self.setText(texto)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        fonte = QFont(self.font())
        fonte.setBold(True)
        self.setFont(fonte)

    def sizeHint(self) -> QSize:
        largura = LARGURA_TRILHO + 12 + self.fontMetrics().horizontalAdvance(self.text())
        return QSize(largura + 4, max(ALTURA_TRILHO, self.fontMetrics().height()) + 8)

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)  # travado: mais apagado, mas mostra se está ligado ou não
        y = (self.height() - ALTURA_TRILHO) / 2
        trilho = QRectF(2, y, LARGURA_TRILHO, ALTURA_TRILHO)
        ligado = self.isChecked()
        p.setPen(QPen(QColor(VERDE if ligado else cor("dica")), 1.5))
        p.setBrush(QColor(VERDE) if ligado else QColor(cor("campo")))
        p.drawRoundedRect(trilho, ALTURA_TRILHO / 2, ALTURA_TRILHO / 2)
        d = ALTURA_TRILHO - 6
        x = trilho.right() - d - 3 if ligado else trilho.left() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff") if ligado else QColor(cor("dica")))
        p.drawEllipse(QRectF(x, y + 3, d, d))
        p.setPen(QColor(cor("texto")))
        p.setFont(self.font())
        texto = QRectF(trilho.right() + 12, 0, self.width() - trilho.right() - 12, self.height())
        p.drawText(texto, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        p.end()
