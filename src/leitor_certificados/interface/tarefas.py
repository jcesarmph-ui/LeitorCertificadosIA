"""Trabalho em segundo plano: o OCR e o treino demoram segundos, e a janela não pode travar.

`Tarefa` roda uma função numa thread própria. A função recebe um `progresso(texto)` para contar o
que está fazendo; o resultado (ou o erro) volta para a janela por sinais do Qt, que cruzam as
threads com segurança — a tela só é mexida na thread principal.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class Tarefa(QThread):
    progresso = Signal(str)
    concluida = Signal(object)
    falhou = Signal(str)

    def __init__(self, funcao: Callable, parent=None):
        super().__init__(parent)
        self._funcao = funcao

    def run(self) -> None:
        try:
            resultado = self._funcao(self.progresso.emit)
        except Exception as erro:
            self.falhou.emit(f"{type(erro).__name__}: {erro}")
        else:
            self.concluida.emit(resultado)
