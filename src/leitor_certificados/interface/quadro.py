"""O quadrinho que abre ao clicar num ponto conferido na folha: a conta inteira do ponto e a
certeza do modelo em cada valor. Fecha ao clicar fora (é uma janela "popup") ou com Esc."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QLabel, QVBoxLayout

from ..conferencia.avaliacao import Resultado
from .estilo import AMARELO, FAIXA_DENTRO, FAIXA_FORA, cor
from .servico import LinhaPonto

# como cada coluna aparece na linha da certeza
NOMES_COLUNAS = {"nominal": "nominal", "encontrado": "encontrado", "erro": "erro",
                 "incerteza": "U", "k": "k", "erro_maximo": "erro máx.", "criterio": "critério"}


class QuadroPonto(QFrame):
    def __init__(self, linha: LinhaPonto, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("quadroPonto")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(
            f"QFrame#quadroPonto {{ background: {cor('campo')}; "
            f"border: 2px solid {cor('contorno')}; border-radius: 6px; }} "
            f"QLabel {{ color: {cor('texto')}; font-size: 12pt; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        titulo = QLabel(f"Ponto {linha.nominal}")
        titulo.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {cor('titulo')};")
        lay.addWidget(titulo)
        if linha.certezas:
            partes = [f"{NOMES_COLUNAS.get(c, c)} {round(100 * v)} %"
                      for c, v in linha.certezas.items()]
            certeza = QLabel("Certeza do modelo: " + " · ".join(partes))
        else:
            certeza = QLabel("Certeza do modelo: —")
        certeza.setStyleSheet(f"color: {cor('dica')}; font-style: italic; font-size: 11pt;")
        certeza.setToolTip("O quanto o modelo tem certeza de que cada valor é o que ele achou")
        lay.addWidget(certeza)
        grade = QGridLayout()
        grade.setHorizontalSpacing(16)
        grade.setVerticalSpacing(3)
        for n, (nome, valor, dica) in enumerate((
            ("Encontrado", linha.encontrado, "Valor que o instrumento indicou"),
            ("Erro", linha.erro, "Encontrado − nominal"),
            ("U", linha.incerteza, "Incerteza expandida informada no certificado"),
            ("Erro − U a erro + U", linha.erro_mais_u,
             "A faixa que o erro pode ocupar, contando a incerteza"),
            ("Tolerância do plano", linha.tolerancia, "Limites aceitos no plano de calibração"),
        )):
            rotulo = QLabel(nome + ":")
            rotulo.setToolTip(dica)
            texto = QLabel(valor)
            texto.setStyleSheet("font-weight: bold;")
            grade.addWidget(rotulo, n, 0)
            grade.addWidget(texto, n, 1)
        lay.addLayout(grade)
        fundo, letra = {Resultado.APROVADO: (FAIXA_DENTRO, "#ffffff"),
                        Resultado.REPROVADO: (FAIXA_FORA, "#ffffff")}.get(
            linha.resultado, (AMARELO, "#000000"))
        parecer = QLabel(linha.resultado.value.upper()
                         + (f" — {linha.motivo}" if linha.motivo else ""))
        parecer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parecer.setStyleSheet(f"background: {fundo}; color: {letra}; font-weight: bold; "
                              "font-size: 14pt; padding: 6px; border-radius: 4px;")
        lay.addWidget(parecer)
        for aviso in linha.avisos:
            texto = QLabel(f"• {aviso}")
            texto.setWordWrap(True)
            texto.setStyleSheet(f"color: {cor('aviso_texto')};")
            lay.addWidget(texto)

    def abrir_em(self, posicao: QPoint) -> None:
        """Mostra perto do clique, sem sair da tela."""
        self.adjustSize()
        x, y = posicao.x() + 14, posicao.y() + 14
        tela = QApplication.screenAt(posicao) or QApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            x = min(x, area.right() - self.width())
            y = min(y, area.bottom() - self.height())
        self.move(x, y)
        self.show()

    def keyPressEvent(self, evento: QKeyEvent) -> None:
        if evento.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(evento)
