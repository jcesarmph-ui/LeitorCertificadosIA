"""Ponto de entrada: cria o aplicativo, aplica o tema escuro e abre a janela maximizada."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .estilo import aplicar_estilo
from .janela import Janela


def main() -> int:
    app = QApplication(sys.argv)
    filtro = aplicar_estilo(app)  # guardado em variável para não ser apagado da memória
    janela = Janela()
    janela.showMaximized()  # sempre maximizada (padrão do usuário)
    janela.iniciar()
    resultado = app.exec()
    del filtro
    return resultado


if __name__ == "__main__":
    sys.exit(main())
