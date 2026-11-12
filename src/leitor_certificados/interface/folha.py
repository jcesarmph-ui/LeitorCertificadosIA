"""A folha do certificado na tela: a imagem, as caixas coloridas por rótulo, os checks da
conferência, a animação de "analisando" e a seleção de palavras para corrigir.

Esta classe só desenha e avisa a janela do que a pessoa fez (sinais `palavras_escolhidas` e
`ponto_clicado`); quem decide e grava é o `servico`.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageOps
from PySide6.QtCore import QElapsedTimer, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
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
    QRadialGradient,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QRubberBand,
)

from ..conferencia.avaliacao import Resultado
from .estilo import AMARELO, VERDE, VERMELHO, cor
from .paletas import cor_rgb, paleta
from .servico import ROTULOS, Analise, LinhaPonto


def cor_do_rotulo(rotulo: str) -> QColor:
    return QColor(*cor_rgb(rotulo))


def cor_do_resultado(resultado: Resultado) -> str:
    """Verde = aprovado, vermelho = reprovado, amarelo = qualquer coisa sem avaliação (aviso)."""
    return {Resultado.APROVADO: VERDE, Resultado.REPROVADO: VERMELHO}.get(resultado, AMARELO)


def tipo_do_rotulo(rotulo: str) -> str:
    """O tipo de valor em MAIÚSCULAS para a dica do mouse: "INCERTEZA (U)", "ERRO", "K"…"""
    if rotulo == "outro":
        return "NÃO É DADO"
    nome = ROTULOS.get(rotulo, rotulo).removeprefix("Ponto: ")
    return nome.replace("fator k", "k").upper()


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
    # número da linha de ponto conferido clicada + onde foi o clique (para abrir o quadrinho)
    ponto_clicado = Signal(int, QPoint)

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
        self._imagem: Image.Image | None = None
        self._caixas: list[CaixaPalavra] = []
        self._linhas: list[LinhaPonto] = []
        self._zonas: list[QGraphicsRectItem] = []  # uma por ponto conferido (dica e clique)
        self._nos_pontos: set[int] = set()  # palavras que estão numa linha conferida
        self._destacar = True  # esmaece o que não é ponto conferido
        self._corrigir = False
        self._origem: QPoint | None = None
        self._clique_ponto: tuple[int, QPoint] | None = None
        self._faixa = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        # animação de "analisando"
        self._relogio = QTimer(self)
        self._relogio.setInterval(33)  # ~30 quadros por segundo: suave e leve
        self._relogio.timeout.connect(self._passo_animacao)
        self._tempo = QElapsedTimer()
        self._raio_x: QGraphicsRectItem | None = None
        self._invertida: QGraphicsPixmapItem | None = None
        self._brilhos: list[tuple[QGraphicsEllipseItem, int, int]] = []
        self._onde_ha_texto: list[tuple[float, float]] = []
        self._sorteio = random.Random(2026)
        self.mostrar_mensagem("Abra um certificado (PDF) ou arraste o arquivo para cá")

    # ------------------------------------------------------------------ conteúdo
    def _limpar(self) -> None:
        self.parar_brilho()
        self._cena.clear()
        self._caixas, self._zonas, self._linhas = [], [], []
        self._nos_pontos = set()
        self._analise = None

    def mostrar_mensagem(self, texto: str) -> None:
        self._limpar()
        self._imagem = None
        self.resetTransform()
        item = self._cena.addSimpleText(texto, QFont("Segoe UI", 14))
        item.setBrush(QBrush(QColor(cor("dica"))))
        self._cena.setSceneRect(item.boundingRect().adjusted(-60, -60, 60, 60))

    def mostrar_imagem(self, imagem: Image.Image) -> None:
        """Só a folha, sem caixas (enquanto o certificado ainda está sendo analisado)."""
        self._limpar()
        self._por_pagina(imagem)
        self.ajustar()

    def _por_pagina(self, imagem: Image.Image) -> None:
        self._imagem = imagem
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
        self._linhas = list(linhas)
        for i, palavra in enumerate(analise.pagina.palavras):
            cx, cy = palavra.centro
            if any(ln.caixa[0] - 0.005 <= cx <= ln.caixa[2] + 0.005
                   and ln.caixa[1] <= cy <= ln.caixa[3] for ln in linhas):
                self._nos_pontos.add(i)
        self._desenhar_checks(linhas, largura, altura)
        if primeira:
            self.ajustar()
        self.set_modo_corrigir(self._corrigir)

    def set_destacar(self, ligado: bool) -> None:
        """Liga/desliga o esmaecer das caixas que não são pontos conferidos."""
        self._destacar = ligado
        self.atualizar_rotulos()

    def atualizar_rotulos(self) -> None:
        """Repinta as caixas conforme os rótulos atuais (depois de uma correção)."""
        analise = self._analise
        if analise is None:
            return
        preencher = paleta().preencher
        esmaecer = self._destacar and bool(self._linhas) and not self._corrigir
        for item in self._caixas:
            i = item.indice
            rotulo = analise.rotulos[i]
            corrigida = i in analise.corrigidas
            certeza = analise.certeza(i)
            palavra = analise.pagina.palavras[i]
            fraca = esmaecer and i not in self._nos_pontos
            if rotulo == "outro":
                # em modo corrigir as palavras "outro" aparecem apagadas, para poder clicar nelas
                cor = QColor(150, 150, 150, 110 if self._corrigir else 0)
                item.setPen(QPen(cor, 1))
                item.setBrush(Qt.BrushStyle.NoBrush)
                situacao = ""
            elif analise.revisar(i):
                # o modelo acha que é um campo, mas tem pouca certeza: tracejado, sem cor dentro
                cor = cor_do_rotulo(rotulo)
                cor.setAlpha(90 if fraca else 200)
                item.setPen(QPen(cor, 2, Qt.PenStyle.DashLine))
                item.setBrush(Qt.BrushStyle.NoBrush)
                situacao = f"REVISAR: certeza baixa ({round(100 * certeza)} %)"
            else:
                cor = cor_do_rotulo(rotulo)
                # quanto mais certo o modelo está, mais forte a cor; em dúvida, fica apagada
                forca = int(30 + 150 * certeza) // (3 if preencher else 9)
                if fraca:
                    cor.setAlpha(80)
                    forca //= 3
                preenchimento = QColor(cor.red(), cor.green(), cor.blue(), forca)
                item.setPen(QPen(cor, 3 if corrigida else 2))
                item.setBrush(QBrush(preenchimento))
                situacao = ("corrigido por você" if corrigida
                            else f"certeza do modelo: {round(100 * certeza)} %")
            # dica do mouse: primeiro o TIPO do valor (com todas as caixas da mesma cor, é
            # assim que se sabe se o número é o erro, a incerteza, o k…)
            item.setToolTip(f"{tipo_do_rotulo(rotulo)}\n“{palavra.texto}”\n{situacao}"
                            .rstrip())
            if item.selecionada:
                # contorno preto tracejado + azul claro: aparece no papel branco e no escuro
                item.setPen(QPen(QColor("#000000"), 3, Qt.PenStyle.DashLine))
                item.setBrush(QBrush(QColor(100, 181, 246, 110)))

    def _desenhar_checks(self, linhas: list[LinhaPonto], largura: int, altura: int) -> None:
        """Para cada ponto conferido: faixa translúcida da cor do resultado atrás da linha
        inteira, contorno grosso e um check grande com contorno e sombra."""
        for linha in linhas:
            e, t, d, b = linha.caixa
            area = QRectF(e * largura, t * altura, (d - e) * largura, (b - t) * altura)
            cor = QColor(cor_do_resultado(linha.resultado))
            lado = max(area.height() * 1.2, 20.0)  # grande, mas sem encostar no vizinho
            x = min(area.right() + 10, largura - lado - 4)
            faixa = QGraphicsRectItem(QRectF(area.left() - 6, area.top() - 1,
                                             x + lado + 4 - (area.left() - 6),
                                             area.height() + 2))
            fundo = QColor(cor)
            fundo.setAlpha(55)
            faixa.setBrush(QBrush(fundo))
            faixa.setPen(QPen(cor, 3))
            faixa.setZValue(0.5)  # atrás das caixas das palavras, na frente da folha
            self._cena.addItem(faixa)
            # área invisível do clique no ponto; sem dica própria, para a dica de cada número
            # (o tipo: erro, incerteza…) aparecer ao passar o mouse
            zona = QGraphicsRectItem(faixa.rect())
            zona.setPen(QPen(Qt.PenStyle.NoPen))
            zona.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            zona.setZValue(2)
            self._cena.addItem(zona)
            self._zonas.append(zona)
            centro_y = area.center().y()
            anel = QGraphicsEllipseItem(QRectF(x - 2, centro_y - lado / 2 - 2, lado + 4, lado + 4))
            anel.setBrush(QBrush(QColor("#000000")))  # anel preto: aparece no papel branco
            anel.setPen(QPen(Qt.PenStyle.NoPen))
            anel.setZValue(3)
            sombra = QGraphicsDropShadowEffect()
            sombra.setBlurRadius(10)
            sombra.setOffset(2, 2)
            sombra.setColor(QColor(0, 0, 0, 170))
            anel.setGraphicsEffect(sombra)
            marca = QGraphicsEllipseItem(QRectF(x, centro_y - lado / 2, lado, lado), anel)
            simbolo, letra = {Resultado.APROVADO: ("✓", "#ffffff"),
                              Resultado.REPROVADO: ("✗", "#ffffff")}.get(
                linha.resultado, ("!", "#000000"))
            marca.setBrush(QBrush(cor))
            marca.setPen(QPen(QColor("#ffffff"), 2.5))  # contorno branco por dentro do preto
            anel.setToolTip(linha.dica())
            texto = QGraphicsSimpleTextItem(simbolo, marca)
            texto.setFont(QFont("Segoe UI", max(int(lado * 0.5), 9), QFont.Weight.Bold))
            texto.setBrush(QBrush(QColor(letra)))
            caixa_texto = texto.boundingRect()
            texto.setPos(x + (lado - caixa_texto.width()) / 2,
                         centro_y - caixa_texto.height() / 2)
            self._cena.addItem(anel)

    # ------------------------------------------------------------------ animação "analisando"
    def iniciar_brilho(self) -> None:
        """Estilo Google Lens: uma faixa tipo raio X desce pela folha (com a imagem levemente
        invertida por onde passa) e pontinhos de luz acendem e apagam, mais onde há texto."""
        self.parar_brilho()
        retangulo = self._cena.sceneRect()
        if self._imagem is None or retangulo.width() <= 0:
            return
        largura, altura = retangulo.width(), retangulo.height()
        self._onde_ha_texto = self._achar_texto(self._imagem)
        faixa = max(altura * 0.09, 40.0)
        # o "raio X": um recorte que só mostra o que está dentro dele
        self._raio_x = QGraphicsRectItem(QRectF(0, 0, largura, faixa))
        self._raio_x.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        self._raio_x.setPen(QPen(Qt.PenStyle.NoPen))
        self._raio_x.setZValue(10)
        invertida = ImageOps.invert(self._imagem.convert("RGB"))
        self._invertida = QGraphicsPixmapItem(QPixmap.fromImage(imagem_para_qt(invertida)),
                                              self._raio_x)
        self._invertida.setOpacity(0.28)  # leve: dá para continuar lendo
        luz = QGraphicsRectItem(QRectF(0, 0, largura, faixa), self._raio_x)
        degrade = QLinearGradient(0, 0, 0, faixa)
        degrade.setColorAt(0.0, QColor(100, 181, 246, 0))
        degrade.setColorAt(0.75, QColor(100, 181, 246, 110))
        degrade.setColorAt(0.93, QColor(225, 245, 255, 220))  # a "linha" mais forte embaixo
        degrade.setColorAt(1.0, QColor(100, 181, 246, 0))
        luz.setBrush(QBrush(degrade))
        luz.setPen(QPen(Qt.PenStyle.NoPen))
        self._cena.addItem(self._raio_x)
        self._tempo.start()
        self._relogio.start()
        self._passo_animacao()

    @staticmethod
    def _achar_texto(imagem: Image.Image) -> list[tuple[float, float]]:
        """Pontos da folha onde há tinta (texto): a imagem é reduzida a uma grade pequena e cada
        quadradinho com algum pixel escuro vira um lugar onde um brilho pode aparecer."""
        largura, altura = imagem.size
        colunas, linhas = 60, max(int(60 * altura / largura), 1)
        pequena = imagem.convert("L").resize((colunas, linhas), Image.Resampling.BOX)
        minimo = imagem.convert("L").resize((colunas, linhas), Image.Resampling.NEAREST)
        lugares = []
        for y in range(linhas):
            for x in range(colunas):
                if pequena.getpixel((x, y)) < 235 or minimo.getpixel((x, y)) < 140:
                    lugares.append(((x + 0.5) * largura / colunas, (y + 0.5) * altura / linhas))
        return lugares

    def _passo_animacao(self) -> None:
        if self._raio_x is None:
            return
        retangulo = self._cena.sceneRect()
        agora = self._tempo.elapsed()
        faixa = self._raio_x.rect().height()
        periodo = 2200
        y = (agora % periodo) / periodo * (retangulo.height() + faixa) - faixa
        self._raio_x.setY(y)
        if self._invertida is not None:
            self._invertida.setY(-y)  # a imagem invertida fica parada; só o recorte anda
        # brilhinhos: nascem, acendem e apagam (opacidade em forma de seno)
        for _ in range(2):
            self._novo_brilho(agora, retangulo)
        vivos = []
        for item, nascimento, vida in self._brilhos:
            idade = agora - nascimento
            if idade >= vida:
                self._cena.removeItem(item)
                continue
            item.setOpacity(math.sin(math.pi * idade / vida))
            vivos.append((item, nascimento, vida))
        self._brilhos = vivos

    def _novo_brilho(self, agora: int, retangulo: QRectF) -> None:
        if len(self._brilhos) > 70:
            return
        sorteio = self._sorteio
        if self._onde_ha_texto and sorteio.random() < 0.8:  # 80 % onde há texto
            x, y = sorteio.choice(self._onde_ha_texto)
            x += sorteio.uniform(-6, 6)
            y += sorteio.uniform(-6, 6)
        else:
            x = sorteio.uniform(0, retangulo.width())
            y = sorteio.uniform(0, retangulo.height())
        raio = sorteio.uniform(5, 12) * max(retangulo.width() / 900, 0.6)
        brilho = QGraphicsEllipseItem(QRectF(x - raio, y - raio, 2 * raio, 2 * raio))
        degrade = QRadialGradient(x, y, raio)
        degrade.setColorAt(0.0, QColor(255, 255, 255, 255))
        degrade.setColorAt(0.35, QColor(140, 200, 255, 200))
        degrade.setColorAt(1.0, QColor(66, 133, 244, 0))
        brilho.setBrush(QBrush(degrade))
        brilho.setPen(QPen(Qt.PenStyle.NoPen))
        brilho.setZValue(11)
        brilho.setOpacity(0.0)
        self._cena.addItem(brilho)
        self._brilhos.append((brilho, agora, sorteio.randint(500, 1200)))

    def brilhando(self) -> bool:
        return self._relogio.isActive()

    def parar_brilho(self) -> None:
        self._relogio.stop()
        for item, _, _ in self._brilhos:
            if item.scene() is not None:
                self._cena.removeItem(item)
        self._brilhos = []
        if self._raio_x is not None and self._raio_x.scene() is not None:
            self._cena.removeItem(self._raio_x)
        self._raio_x = None
        self._invertida = None

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

    def wheelEvent(self, evento: QWheelEvent) -> None:
        """Ctrl + roda = zoom centrado no ponteiro; a roda sozinha só rola."""
        if evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
            passos = evento.angleDelta().y() / 120
            if passos:
                self.zoom(1.15 ** passos)  # AnchorUnderMouse mantém o ponto sob o ponteiro
            evento.accept()
            return
        super().wheelEvent(evento)

    # ------------------------------------------------------------------ cliques
    def linha_em(self, ponto_cena) -> int | None:
        """Qual ponto conferido está neste lugar da folha (ou None)."""
        for n, zona in enumerate(self._zonas):
            if zona.rect().contains(ponto_cena):
                return n
        return None

    def centro_do_ponto(self, n: int) -> QPoint:
        """Onde fica, na tela, o meio da linha do ponto `n` (para testes e fotos)."""
        local = self.mapFromScene(self._zonas[n].rect().center())
        return self.viewport().mapToGlobal(local)

    # ------------------------------------------------------------------ modo corrigir
    def set_modo_corrigir(self, ligado: bool) -> None:
        self._corrigir = ligado
        self.setDragMode(QGraphicsView.DragMode.NoDrag if ligado
                         else QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if ligado
                                  else Qt.CursorShape.OpenHandCursor)
        for zona in self._zonas:  # a dica do ponto atrapalharia a dica da palavra
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
        if not self._corrigir and evento.button() == Qt.MouseButton.LeftButton:
            n = self.linha_em(self.mapToScene(evento.position().toPoint()))
            self._clique_ponto = None if n is None else (n, evento.position().toPoint())
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        if self._origem is not None:
            self._faixa.setGeometry(QRect(self._origem, evento.position().toPoint()).normalized())
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:
        if self._clique_ponto is not None:
            n, onde = self._clique_ponto
            self._clique_ponto = None
            super().mouseReleaseEvent(evento)
            # só conta como clique se o mouse quase não andou (senão foi arrastar a folha)
            if (evento.position().toPoint() - onde).manhattanLength() < 6:
                self.ponto_clicado.emit(n, evento.globalPosition().toPoint())
            return
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
