"""Ponto de entrada: cria o aplicativo, aplica o tema e abre a janela maximizada."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from .estilo import aplicar_estilo
from .janela import Janela


def main() -> int:
    app = QApplication(sys.argv)
    filtro = aplicar_estilo(app)  # guardado em variável para não ser apagado da memória
    janela = Janela()
    # sempre maximizada (padrão do usuário). O estado é pedido antes e depois de mostrar: no
    # Windows, se a janela ainda não tinha sido medida, o primeiro pedido podia se perder.
    janela.setWindowState(janela.windowState() | Qt.WindowState.WindowMaximized)
    janela.showMaximized()
    QTimer.singleShot(0, lambda: janela.isMaximized() or janela.showMaximized())
    janela.iniciar()
    resultado = app.exec()
    del filtro
    return resultado


if __name__ == "__main__":
    sys.exit(main())
