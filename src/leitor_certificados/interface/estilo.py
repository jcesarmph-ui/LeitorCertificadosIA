"""A aparência do programa: os temas de cor da interface e o filtro da roda do mouse.

Há várias opções de tema em `TEMAS` (o usuário vai escolher uma); a escolhida fica em
`TEMA_ATUAL`. O que muda de um tema para outro é só o "fundo" (janela, caixas, campos, texto).
As cores com significado são as mesmas em todos (regra do usuário): vermelho só no botão
principal e em erros; amarelo em todo aviso; verde no que está certo. Nada de neon ou brilho.
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

# --- cores com significado: iguais em todos os temas
VERMELHO = "#c62828"
VERMELHO_HOVER = "#e53935"
FAIXA_FORA = "#b71c1c"
AMARELO = "#ffd54f"  # fundo de aviso (sempre com letra preta)
VERDE = "#43a047"
FAIXA_DENTRO = "#1b5e20"

# --- os temas (o "fundo" da interface). Cada chave é usada no estilo abaixo.
TEMAS: dict[str, dict[str, str]] = {
    # o padrão claro do usuário (cinza): já usado nos outros programas dele
    "cinza_claro": {
        "nome": "Cinza claro", "fundo": "#c9c9c9", "caixa": "#dedede", "campo": "#f5f5f5",
        "borda_campo": "#8a8a8a", "contorno": "#2b2b2b", "titulo": "#111111",
        "texto": "#1a1a1a", "selecao": "#b5b5b5", "pressionado": "#a5a5a5",
        "desabilitado": "#8a8a8a", "dica": "#4f4f4f", "aviso_texto": "#8d6e00",
        "erro_texto": "#c62828", "folha_fundo": "#a9a9a9", "rolagem": "#8f8f8f"},
    # grafite: escuro, mas não preto (cinza-chumbo)
    "grafite": {
        "nome": "Grafite", "fundo": "#1e1f22", "caixa": "#2b2d31", "campo": "#383a40",
        "borda_campo": "#4e5058", "contorno": "#b5bac1", "titulo": "#ffffff",
        "texto": "#f2f3f5", "selecao": "#4e5058", "pressionado": "#5c5f68",
        "desabilitado": "#7a7d85", "dica": "#a0a4ab", "aviso_texto": "#ffd54f",
        "erro_texto": "#ef5350", "folha_fundo": "#26272b", "rolagem": "#5c5f68"},
    # azul-marinho escuro
    "azul_marinho": {
        "nome": "Azul-marinho", "fundo": "#0f1a2b", "caixa": "#16243a", "campo": "#1f3150",
        "borda_campo": "#34507a", "contorno": "#9db7dd", "titulo": "#ffffff",
        "texto": "#eef3fb", "selecao": "#2e4a75", "pressionado": "#3a5a8a",
        "desabilitado": "#6c7f9c", "dica": "#9fb0c8", "aviso_texto": "#ffd54f",
        "erro_texto": "#ff6b6b", "folha_fundo": "#0b1422", "rolagem": "#3a5a8a"},
    # claro azulado: quase branco, com detalhes em azul-acinzentado
    "claro_azulado": {
        "nome": "Claro azulado", "fundo": "#e3e9f1", "caixa": "#ffffff", "campo": "#f5f8fc",
        "borda_campo": "#b8c4d4", "contorno": "#5b7090", "titulo": "#0d2a4d",
        "texto": "#1b2533", "selecao": "#cfdcec", "pressionado": "#b9cbe2",
        "desabilitado": "#9aa6b5", "dica": "#5a6676", "aviso_texto": "#8d6e00",
        "erro_texto": "#c62828", "folha_fundo": "#ccd5e1", "rolagem": "#a9b6c8"},
    # o preto puro original (guardado; o usuário pediu outro por enquanto)
    "preto": {
        "nome": "Preto", "fundo": "#000000", "caixa": "#0a0a0a", "campo": "#161616",
        "borda_campo": "#3a3a3a", "contorno": "#e0e0e0", "titulo": "#ffffff",
        "texto": "#f0f0f0", "selecao": "#424242", "pressionado": "#2a2a2a",
        "desabilitado": "#6a6a6a", "dica": "#9e9e9e", "aviso_texto": "#ffd54f",
        "erro_texto": "#ef5350", "folha_fundo": "#1c1c1c", "rolagem": "#4a4a4a"},
}

TEMA_ATUAL = "claro_azulado"  # escolha do usuário em 2026-11-12


def cor(nome: str) -> str:
    """Uma cor do tema em uso (ex.: cor("campo"))."""
    return TEMAS[TEMA_ATUAL][nome]


def montar_estilo(chave: str | None = None) -> str:
    t = TEMAS[chave or TEMA_ATUAL]
    return f"""
* {{ font-family: "Segoe UI"; font-size: 13pt; color: {t['texto']}; }}
QMainWindow, QWidget#raiz, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {t['fundo']};
}}
QGroupBox {{
    background: {t['caixa']}; border: 1px solid {t['contorno']}; border-radius: 4px;
    margin-top: 14px; padding: 10px 8px 8px 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 6px; color: {t['titulo']};
    font-weight: bold;
}}
QLabel {{ background: transparent; }}
QLabel#titulo {{
    font-size: 22pt; font-weight: bold; letter-spacing: 3px; color: {t['titulo']};
}}
QLabel#versao {{ color: {t['dica']}; font-size: 11pt; }}
QLabel#dica {{ color: {t['dica']}; font-style: italic; }}
QLabel#avisos {{ font-size: 12pt; }}
QLabel#parecer {{ font-size: 28pt; font-weight: bold; border-radius: 4px; padding: 10px; }}
QPushButton {{
    background: {t['campo']}; border: 1px solid {t['contorno']}; border-radius: 4px;
    padding: 7px 16px;
}}
QPushButton:hover {{ background: {t['selecao']}; }}
QPushButton:pressed {{ background: {t['pressionado']}; }}
QPushButton:checked {{ background: {t['selecao']}; border: 2px solid {t['titulo']}; }}
QPushButton:disabled {{ color: {t['desabilitado']}; border-color: {t['borda_campo']}; }}
QPushButton#principal {{
    background: {VERMELHO}; border: 1px solid {VERMELHO}; color: #ffffff; font-size: 20pt;
    font-weight: bold; padding: 8px 28px;
}}
QPushButton#principal:hover {{ background: {VERMELHO_HOVER}; }}
QPushButton#principal:disabled {{ background: #9e5a5a; color: #f0dada; }}
QPushButton#zoom {{ padding: 4px 12px; font-weight: bold; }}
QTableWidget {{
    background: {t['campo']}; border: 1px solid {t['borda_campo']};
    gridline-color: {t['borda_campo']}; selection-background-color: {t['selecao']};
    selection-color: {t['texto']};
}}
QHeaderView::section {{
    background: {t['caixa']}; color: {t['titulo']}; border: 1px solid {t['borda_campo']};
    padding: 4px; font-weight: bold;
}}
QLineEdit, QComboBox {{
    background: {t['campo']}; color: {t['texto']}; border: 1px solid {t['borda_campo']};
    border-radius: 3px; padding: 4px 8px; selection-background-color: {t['selecao']};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t['contorno']}; }}
QComboBox QAbstractItemView {{
    background: {t['campo']}; color: {t['texto']}; border: 1px solid {t['contorno']};
    selection-background-color: {t['selecao']}; selection-color: {t['texto']};
}}
QGraphicsView {{ background: {t['folha_fundo']}; border: 1px solid {t['borda_campo']}; }}
QScrollBar:vertical {{ background: {t['caixa']}; width: 14px; }}
QScrollBar:horizontal {{ background: {t['caixa']}; height: 14px; }}
QScrollBar::handle {{
    background: {t['rolagem']}; border-radius: 4px; min-height: 24px; min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMenu {{ background: {t['campo']}; color: {t['texto']}; border: 1px solid {t['contorno']}; }}
QMenu::item {{ padding: 5px 24px; }}
QMenu::item:selected {{ background: {t['selecao']}; color: {t['texto']}; }}
QToolTip {{
    background: {t['campo']}; color: {t['texto']}; border: 1px solid {t['contorno']};
    padding: 4px;
}}
QProgressBar {{
    background: {t['campo']}; border: 1px solid {t['borda_campo']}; border-radius: 3px;
    height: 10px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {t['dica']}; }}
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
    """Aplica o tema em uso e instala o filtro da roda; guarde o filtro (senão é apagado)."""
    app.setStyle("Fusion")
    app.setStyleSheet(montar_estilo())
    filtro = FiltroRodaDoMouse(app)
    app.installEventFilter(filtro)
    return filtro
