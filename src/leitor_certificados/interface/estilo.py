"""A aparência do programa: tema escuro do padrão do usuário e o filtro da roda do mouse.

Cores com significado (regra do usuário): vermelho só no botão principal e em erros; amarelo em
todo aviso; verde no que está certo. Nada de neon ou brilho.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QTabBar,
    QWidget,
)

FUNDO = "#000000"
CAIXA = "#0a0a0a"
CAMPO = "#161616"
BORDA_CAMPO = "#3a3a3a"
CONTORNO = "#e0e0e0"
TEXTO = "#f0f0f0"
SELECAO = "#424242"
VERMELHO = "#c62828"
VERMELHO_HOVER = "#e53935"
VERMELHO_TEXTO = "#ef5350"
FAIXA_FORA = "#b71c1c"
AMARELO = "#ffd54f"
VERDE = "#43a047"
FAIXA_DENTRO = "#1b5e20"
LINK = "#64b5f6"
DICA = "#9e9e9e"

ESTILO = f"""
* {{ font-family: "Segoe UI"; font-size: 13pt; color: {TEXTO}; }}
QMainWindow, QWidget#raiz, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {FUNDO};
}}
QGroupBox {{
    background: {CAIXA}; border: 1px solid {CONTORNO}; border-radius: 4px;
    margin-top: 14px; padding: 10px 8px 8px 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #ffffff; font-weight: bold;
}}
QLabel {{ background: transparent; }}
QLabel#titulo {{ font-size: 22pt; font-weight: bold; letter-spacing: 3px; color: #ffffff; }}
QLabel#versao {{ color: {DICA}; font-size: 11pt; }}
QLabel#dica {{ color: {DICA}; font-style: italic; }}
QLabel#avisos {{ font-size: 12pt; }}
QLabel#parecer {{ font-size: 28pt; font-weight: bold; border-radius: 4px; padding: 10px; }}
QPushButton {{
    background: {CAMPO}; border: 1px solid {CONTORNO}; border-radius: 4px; padding: 7px 16px;
}}
QPushButton:hover {{ background: {SELECAO}; }}
QPushButton:pressed {{ background: #2a2a2a; }}
QPushButton:checked {{ background: {SELECAO}; border: 2px solid #ffffff; }}
QPushButton:disabled {{ color: #6a6a6a; border-color: #3a3a3a; }}
QPushButton#principal {{
    background: {VERMELHO}; border: 1px solid {VERMELHO}; color: #ffffff; font-size: 20pt;
    font-weight: bold; padding: 8px 28px;
}}
QPushButton#principal:hover {{ background: {VERMELHO_HOVER}; }}
QPushButton#principal:disabled {{ background: #3a1414; color: #8a6a6a; }}
QPushButton#zoom {{ padding: 4px 12px; font-weight: bold; }}
QTableWidget {{
    background: {CAMPO}; border: 1px solid {BORDA_CAMPO}; gridline-color: {BORDA_CAMPO};
    selection-background-color: {SELECAO};
}}
QHeaderView::section {{
    background: {CAIXA}; color: #ffffff; border: 1px solid {BORDA_CAMPO}; padding: 4px;
    font-weight: bold;
}}
QGraphicsView {{ background: #1c1c1c; border: 1px solid {BORDA_CAMPO}; }}
QScrollBar:vertical {{ background: {CAIXA}; width: 14px; }}
QScrollBar:horizontal {{ background: {CAIXA}; height: 14px; }}
QScrollBar::handle {{ background: #4a4a4a; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMenu {{ background: {CAMPO}; border: 1px solid {CONTORNO}; }}
QMenu::item {{ padding: 5px 24px; }}
QMenu::item:selected {{ background: {SELECAO}; }}
QToolTip {{
    background: {CAMPO}; color: {TEXTO}; border: 1px solid {CONTORNO}; padding: 4px;
}}
QProgressBar {{
    background: {CAMPO}; border: 1px solid {BORDA_CAMPO}; border-radius: 3px; height: 10px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: #9e9e9e; }}
"""


class FiltroRodaDoMouse(QObject):
    """A roda do mouse só rola a tela: nunca muda lista, número ou aba por acidente.

    Quando a roda gira sobre um campo desses, o evento é desviado para a área de rolagem que o
    contém (se houver); se não houver, é simplesmente descartado."""

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if evento.type() == QEvent.Type.Wheel and isinstance(
                objeto, QComboBox | QAbstractSpinBox | QTabBar):
            pai = objeto.parentWidget() if isinstance(objeto, QWidget) else None
            while pai is not None and not isinstance(pai, QAbstractScrollArea):
                pai = pai.parentWidget()
            if pai is not None:
                QApplication.sendEvent(pai.viewport(), evento)
            return True
        return False


def aplicar_estilo(app: QApplication) -> FiltroRodaDoMouse:
    """Aplica o tema escuro e instala o filtro da roda; guarde o filtro (senão é apagado)."""
    app.setStyle("Fusion")
    app.setStyleSheet(ESTILO)
    filtro = FiltroRodaDoMouse(app)
    app.installEventFilter(filtro)
    return filtro
