"""A folha do certificado na tela: a imagem, as caixas coloridas por rótulo, os checks da
conferência, o "brilho" de quem está analisando e a seleção de palavras para corrigir.

Esta classe só desenha e avisa a janela do que a pessoa fez (sinal `palavras_escolhidas`); quem
decide e grava é o `servico`.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QRubberBand,
)

from ..conferencia.avaliacao import Resultado
from .estilo import AMARELO, DICA, VERDE, VERMELHO
from .servico import ROTULOS, Analise, LinhaPonto

# Cores das caixas por rótulo, na paleta do PlayStation 1 (pedido do usuário): os quatro botões
# (triângulo verde, círculo vermelho, xis azul, quadrado rosa), o amarelo e o laranja do logo e o
# cinza do console. Todas ficam aqui, num lugar só, para trocar fácil. Os rótulos que não têm cor
# própria ganham o rosa do quadrado.
CORES = {
    "ponto.nominal": (46, 111, 216),      # azul do xis
    "ponto.encontrado": (47, 168, 79),    # verde do triângulo
    "ponto.erro": (242, 169, 0),          # amarelo do logo
    "ponto.incerteza": (214, 50, 47),     # vermelho do círculo
    "ponto.k": (140, 90, 190),            # roxo
    "ponto.erro_maximo": (232, 110, 20),  # laranja do logo
    "ponto.criterio": (170, 120, 60),
    "codigo": (0, 140, 190),              # azul-petróleo do logo
    "tipo": (110, 130, 30),
    "laboratorio": (120, 120, 130),       # cinza do console
}
COR_PADRAO = (217, 112, 168)              # rosa do quadrado


def cor_do_rotulo(rotulo: str) -> QColor:
    return QColor(*CORES.get(rotulo, COR_PADRAO))


def imagem_para_qt(imagem: Image.Image) -> QImage:
    largura, altura = imagem.size
    dados = imagem.convert("RGB").tobytes()
    return QImage(dados, largura, altura, 3 * largura, QImage.Format.Format_RGB888).copy()


class CaixaPalavra(QGraphicsRectItem):
    """O retângulo de uma palavra lida; guarda o número dela (o `i` do .palavras.json)."""

    def __init__(self, indice: int, retangulo: QRectF):
        super().__init__(retangulo)
        self.indice = indice
        self.selecionada = False


class FolhaView(QGraphicsView):
    # índices das palavras escolhidas + onde o mouse soltou (para abrir a lista ali)
    palavras_escolhidas = Signal(list, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cena = QGraphicsScene(self)
        self.setScene(self._cena)
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(QSize(380, 300))
        self._analise: Analise | None = None
        self._caixas: list[CaixaPalavra] = []
        self._extras: list[QGraphicsItem] = []  # checks e áreas dos pontos
        self._areas_pontos: list[QGraphicsRectItem] = []
        self._corrigir = False
        self._origem: QPoint | None = None
        self._faixa = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._brilho: QGraphicsRectItem | None = None
        self._animacao: QVariantAnimation | None = None
        self.mostrar_mensagem("Abra um certificado (PDF) ou arraste o arquivo para cá")

    # ------------------------------------------------------------------ conteúdo
    def _limpar(self) -> None:
        self.parar_brilho()
        self._cena.clear()
        self._caixas, self._extras, self._areas_pontos = [], [], []
        self._analise = None

    def mostrar_mensagem(self, texto: str) -> None:
        self._limpar()
        self.resetTransform()
        item = self._cena.addSimpleText(texto, QFont("Segoe UI", 14))
        item.setBrush(QBrush(QColor(DICA)))
        self._cena.setSceneRect(item.boundingRect().adjusted(-60, -60, 60, 60))

    def mostrar_imagem(self, imagem: Image.Image) -> None:
        """Só a folha, sem caixas (enquanto o certificado ainda está sendo analisado)."""
        self._limpar()
        self._por_pagina(imagem)
        self.ajustar()

    def _por_pagina(self, imagem: Image.Image) -> None:
        pixmap = QPixmap.fromImage(imagem_para_qt(imagem))
        self._cena.addPixmap(pixmap).setZValue(0)
        self._cena.setSceneRect(QRectF(pixmap.rect()))

    def mostrar_analise(self, analise: Analise, linhas: list[LinhaPonto]) -> None:
        """A folha com as caixas coloridas e, se houve conferência, os checks."""
        primeira = self._analise is None or self._analise.caminho != analise.caminho
        self._limpar()
        self._analise = analise
        self._por_pagina(analise.imagem)
        largura, altura = analise.imagem.size
        for i, palavra in enumerate(analise.pagina.palavras):
            e, t, d, b = palavra.caixa
            item = CaixaPalavra(i, QRectF(e * largura, t * altura, (d - e) * largura,
                                          (b - t) * altura))
            item.setZValue(1)
            self._cena.addItem(item)
            self._caixas.append(item)
        self.atualizar_rotulos()
        self._desenhar_checks(linhas, largura, altura)
        if primeira:
            self.ajustar()
        self.set_modo_corrigir(self._corrigir)

    def atualizar_rotulos(self) -> None:
        """Repinta as caixas conforme os rótulos atuais (depois de uma correção)."""
        analise = self._analise
        if analise is None:
            return
        for item in self._caixas:
            i = item.indice
            rotulo = analise.rotulos[i]
            corrigida = i in analise.corrigidas
            certeza = analise.certeza(i)
            palavra = analise.pagina.palavras[i]
            if rotulo == "outro":
                # em modo corrigir as palavras "outro" aparecem apagadas, para poder clicar nelas
                cor = QColor(150, 150, 150, 110 if self._corrigir else 0)
                item.setPen(QPen(cor, 1))
                item.setBrush(Qt.BrushStyle.NoBrush)
            else:
                cor = cor_do_rotulo(rotulo)
                # quanto mais certo o modelo está, mais forte a cor; em dúvida, fica apagada
                forca = int(30 + 150 * certeza)
                preenchimento = QColor(cor.red(), cor.green(), cor.blue(), forca // 3)
                item.setPen(QPen(cor, 3 if corrigida else 2))
                item.setBrush(QBrush(preenchimento))
            origem = ("corrigido por você" if corrigida
                      else f"certeza do modelo: {round(100 * certeza)} %")
            item.setToolTip(f"“{palavra.texto}”\n{ROTULOS.get(rotulo, rotulo)}\n{origem}")
            if item.selecionada:
                # contorno preto tracejado + azul claro: aparece no papel branco e no escuro
                item.setPen(QPen(QColor("#000000"), 3, Qt.PenStyle.DashLine))
                item.setBrush(QBrush(QColor(100, 181, 246, 110)))

    def _desenhar_checks(self, linhas: list[LinhaPonto], largura: int, altura: int) -> None:
        for linha in linhas:
            e, t, d, b = linha.caixa
            area = QRectF(e * largura, t * altura, (d - e) * largura, (b - t) * altura)
            zona = QGraphicsRectItem(area.adjusted(-2, -2, 2, 2))
            zona.setPen(QPen(Qt.PenStyle.NoPen))
            zona.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            zona.setZValue(2)
            zona.setToolTip(linha.dica())
            self._cena.addItem(zona)
            self._areas_pontos.append(zona)
            lado = max(area.height() * 1.15, 18.0)
            x = min(area.right() + 6, largura - lado - 2)
            marca = QGraphicsEllipseItem(QRectF(x, area.center().y() - lado / 2, lado, lado))
            fundo, simbolo, letra = {
                Resultado.APROVADO: (VERDE, "✓", "#ffffff"),
                Resultado.REPROVADO: (VERMELHO, "✗", "#ffffff"),
            }.get(linha.resultado, (AMARELO, "!", "#000000"))  # sem avaliação = aviso amarelo
            marca.setBrush(QBrush(QColor(fundo)))
            marca.setPen(QPen(QColor("#ffffff"), 1.5))
            marca.setZValue(3)
            marca.setToolTip(linha.dica())
            texto = QGraphicsSimpleTextItem(simbolo, marca)
            texto.setFont(QFont("Segoe UI", max(int(lado * 0.45), 8), QFont.Weight.Bold))
            texto.setBrush(QBrush(QColor(letra)))
            caixa_texto = texto.boundingRect()
            texto.setPos(x + (lado - caixa_texto.width()) / 2,
                         marca.rect().center().y() - caixa_texto.height() / 2)
            self._cena.addItem(marca)
            self._extras.append(marca)

    # ------------------------------------------------------------------ brilho de "analisando"
    def iniciar_brilho(self) -> None:
        """Faixa azul clara (branco sumiria no papel) que desce pela folha, como o Google Lens."""
        self.parar_brilho()
        retangulo = self._cena.sceneRect()
        faixa = max(retangulo.height() * 0.10, 40.0)
        degrade = QLinearGradient(0, 0, 0, faixa)
        degrade.setColorAt(0.0, QColor(100, 181, 246, 0))
        degrade.setColorAt(0.5, QColor(100, 181, 246, 120))
        degrade.setColorAt(1.0, QColor(100, 181, 246, 0))
        self._brilho = QGraphicsRectItem(QRectF(retangulo.left(), 0, retangulo.width(), faixa))
        self._brilho.setBrush(QBrush(degrade))
        self._brilho.setPen(QPen(Qt.PenStyle.NoPen))
        self._brilho.setZValue(10)
        self._cena.addItem(self._brilho)
        self._animacao = QVariantAnimation(self)
        self._animacao.setStartValue(retangulo.top() - faixa)
        self._animacao.setEndValue(retangulo.bottom())
        self._animacao.setDuration(1800)
        self._animacao.setLoopCount(-1)
        self._animacao.valueChanged.connect(lambda y: self._brilho and self._brilho.setY(y))
        self._animacao.start()

    def parar_brilho(self) -> None:
        if self._animacao is not None:
            self._animacao.stop()
            self._animacao = None
        if self._brilho is not None and self._brilho.scene() is not None:
            self._cena.removeItem(self._brilho)
        self._brilho = None

    # ------------------------------------------------------------------ zoom
    def zoom(self, fator: float) -> None:
        self.scale(fator, fator)

    def ajustar(self) -> None:
        """Cabe a largura da folha na janela (a rolagem cuida da altura)."""
        retangulo = self._cena.sceneRect()
        if retangulo.width() <= 0:
            return
        self.resetTransform()
        escala = max(self.viewport().width() - 4, 100) / retangulo.width()
        self.scale(escala, escala)

    # ------------------------------------------------------------------ modo corrigir
    def set_modo_corrigir(self, ligado: bool) -> None:
        self._corrigir = ligado
        self.setDragMode(QGraphicsView.DragMode.NoDrag if ligado
                         else QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if ligado
                                  else Qt.CursorShape.OpenHandCursor)
        for zona in self._areas_pontos:  # a dica do ponto atrapalharia a dica da palavra
            zona.setVisible(not ligado)
        if not ligado:
            self.limpar_selecao()
        self.atualizar_rotulos()

    def limpar_selecao(self) -> None:
        for item in self._caixas:
            item.selecionada = False
        self.atualizar_rotulos()

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        if self._corrigir and evento.button() == Qt.MouseButton.LeftButton and self._caixas:
            self.limpar_selecao()
            self._origem = evento.position().toPoint()
            self._faixa.setGeometry(QRect(self._origem, QSize()))
            self._faixa.show()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        if self._origem is not None:
            self._faixa.setGeometry(QRect(self._origem, evento.position().toPoint()).normalized())
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:
        if self._origem is None:
            super().mouseReleaseEvent(evento)
            return
        retangulo = QRect(self._origem, evento.position().toPoint()).normalized()
        self._origem = None
        self._faixa.hide()
        indices = self._palavras_em(retangulo)
        for item in self._caixas:
            item.selecionada = item.indice in indices
        self.atualizar_rotulos()
        if indices:
            self.palavras_escolhidas.emit(indices, evento.globalPosition().toPoint())

    def _palavras_em(self, retangulo: QRect) -> list[int]:
        """Clique solto = a palavra embaixo dele; arrastar = as palavras cujo centro caiu dentro."""
        if retangulo.width() < 5 and retangulo.height() < 5:
            ponto = self.mapToScene(retangulo.center())
            achadas = [c for c in self._caixas if c.rect().contains(ponto)]
            if not achadas:  # caixa fina: aceita um clique perto
                achadas = [c for c in self._caixas
                           if c.rect().adjusted(-4, -4, 4, 4).contains(ponto)]
            return [achadas[0].indice] if achadas else []
        area = self.mapToScene(retangulo).boundingRect()
        return [c.indice for c in self._caixas if area.contains(c.rect().center())]

    def selecionar(self, indices: list[int]) -> None:
        """Marca palavras como selecionadas (usado pelos testes e pela janela)."""
        for item in self._caixas:
            item.selecionada = item.indice in indices
        self.atualizar_rotulos()

