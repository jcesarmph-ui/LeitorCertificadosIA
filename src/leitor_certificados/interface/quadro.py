"""O quadrinho que abre ao clicar na folha. Fecha ao clicar fora (é uma janela "popup") ou com Esc.

- clique numa linha de ponto conferido: a conta inteira do ponto e a certeza do modelo em cada
  valor; se o clique foi numa palavra, embaixo vêm os botões para corrigir aquela palavra;
- clique numa palavra fora dos pontos: só a palavra e os botões "Corrigir rótulo" e
  "Corrigir texto" (o quadrinho pergunta antes; a lista de rótulos só abre se a pessoa quiser).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..conferencia.avaliacao import Resultado
from .estilo import AMARELO, FAIXA_DENTRO, FAIXA_FORA, cor
from .servico import LinhaPonto

# como cada coluna aparece na linha da certeza
NOMES_COLUNAS = {"nominal": "nominal", "encontrado": "encontrado", "erro": "erro",
                 "incerteza": "U", "k": "k", "erro_maximo": "erro máx.", "criterio": "critério"}


class QuadroPonto(QFrame):
    corrigir_rotulo = Signal(int)  # índice da palavra
    corrigir_texto = Signal(int)

    def __init__(self, linha: LinhaPonto | None, parent=None,
                 palavra: tuple[int, str, str] | None = None,
                 ordem: tuple[int, int] | None = None):
        """`palavra` = (índice, texto, TIPO) da palavra clicada, ou None.
        `ordem` = (número do ponto, quantos pontos), para o título "Ponto 3 de 9"."""
        self._ordem = ordem
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
        if linha is not None:
            self._montar_ponto(lay, linha)
        if palavra is not None:
            self._montar_palavra(lay, palavra, separar=linha is not None)

    def _montar_ponto(self, lay: QVBoxLayout, linha: LinhaPonto) -> None:
        titulo = QLabel(f"Ponto {self._ordem[0]} de {self._ordem[1]} — nominal {linha.nominal}"
                        if self._ordem else f"Ponto {linha.nominal}")
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
            ("Erro ± U", linha.erro_mais_u,
             "O erro somado à incerteza, do lado mais perto da tolerância "
             "(igual ao programa de calibração); \"± U\" quando o erro é zero"),
            ("Tolerância do plano", linha.tolerancia, "Limites aceitos no plano de calibração"),
            *((("Critério do certificado",
                linha.criterio + (" (diferente do plano)" if linha.criterio_diferente else ""),
                "Critério de aceitação ± que o laboratório usou (só avisa; não muda o parecer)"),)
              if linha.criterio else ()),
        )):
            rotulo = QLabel(nome + ":")
            rotulo.setToolTip(dica)
            texto = QLabel(valor)
            amarelo = nome == "Critério do certificado" and linha.criterio_diferente
            texto.setStyleSheet("font-weight: bold;"
                                + (f" color: {cor('aviso_texto')};" if amarelo else ""))
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

    def _montar_palavra(self, lay: QVBoxLayout, palavra: tuple[int, str, str],
                        separar: bool) -> None:
        indice, texto, tipo = palavra
        if separar:
            linha = QFrame()
            linha.setFrameShape(QFrame.Shape.HLine)
            linha.setStyleSheet(f"color: {cor('borda_campo')};")
            lay.addWidget(linha)
        nome = QLabel(f"“{texto}” — {tipo}")
        nome.setStyleSheet("font-weight: bold;")
        lay.addWidget(nome)
        pergunta = QLabel("O modelo errou esta palavra?")
        pergunta.setStyleSheet(f"color: {cor('dica')}; font-style: italic; font-size: 11pt;")
        lay.addWidget(pergunta)
        botoes = QHBoxLayout()
        self.botao_rotulo = QPushButton("Corrigir rótulo")
        self.botao_rotulo.setToolTip("Escolher o que esta palavra é (erro, incerteza, código…)")
        self.botao_texto = QPushButton("Corrigir texto")
        self.botao_texto.setToolTip("Escrever o que realmente está escrito (o OCR leu errado). "
                                    "Atalho: duplo clique na palavra.")
        self.botao_rotulo.clicked.connect(lambda: self._escolheu(self.corrigir_rotulo, indice))
        self.botao_texto.clicked.connect(lambda: self._escolheu(self.corrigir_texto, indice))
        botoes.addWidget(self.botao_rotulo)
        botoes.addWidget(self.botao_texto)
        lay.addLayout(botoes)

    def _escolheu(self, sinal, indice: int) -> None:
        sinal.emit(indice)
        self.close()

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
