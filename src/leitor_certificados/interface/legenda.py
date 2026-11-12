"""A legenda das cores da folha (rótulo → cor), sempre visível embaixo da folha, e o quadradinho
de cor usado na lista de rótulos do modo Corrigir."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from .paletas import LEGENDA, REVISAR, cor_rgb, paleta

COLUNAS = 5  # 21 itens em 5 colunas = 5 linhas curtas, sem abrir buraco na tela


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


class Legenda(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        grade = QGridLayout(self)
        grade.setContentsMargins(2, 2, 2, 2)
        grade.setHorizontalSpacing(14)
        grade.setVerticalSpacing(2)
        itens = [(nome, rotulos[0], False) for nome, rotulos in LEGENDA]
        itens.append((REVISAR, "ponto.nominal", True))
        self.nomes: list[str] = []
        for n, (nome, rotulo, tracejada) in enumerate(itens):
            linha = QHBoxLayout()
            linha.setSpacing(5)
            quadrado = QLabel()
            quadrado.setPixmap(amostra(rotulo, 14, tracejada))
            texto = QLabel(nome)
            texto.setStyleSheet("font-size: 10pt;")
            if tracejada:
                texto.setToolTip("Contorno tracejado: o modelo acha que é um campo, mas tem "
                                 "pouca certeza (menos de 50 %). A conferência ignora a palavra; "
                                 "corrija se for o caso.")
            linha.addWidget(quadrado)
            linha.addWidget(texto, 1)
            grade.addLayout(linha, n // COLUNAS, n % COLUNAS)
            self.nomes.append(nome)
