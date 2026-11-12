"""A janela principal: botões em cima, a folha à esquerda, o parecer e os pontos à direita.

A janela só mostra e chama o `servico`. Nada de regra de negócio aqui: quem lê, confere, corrige
e treina é o `servico` (e os módulos de leitura, aprendizado e conferência por baixo dele).
Tudo o que demora roda numa `Tarefa` (thread), para a tela nunca travar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..conferencia.avaliacao import Resultado
from .estilo import (
    AMARELO,
    CAMPO,
    DICA,
    FAIXA_DENTRO,
    FAIXA_FORA,
    VERDE,
    VERMELHO_TEXTO,
)
from .folha import FolhaView
from .servico import (
    ROTULOS,
    Analise,
    LinhaPonto,
    Servico,
    descrever_pontos,
    gravar_correcao,
    renderizar_folha,
)
from .tarefas import Tarefa

COLUNAS = ["Nominal", "Encontrado", "Erro", "U", "Erro ± U", "Tolerância do plano", "Resultado"]
DICAS_COLUNAS = {
    "U": "Incerteza expandida de medição, informada no certificado",
    "Erro ± U": "A faixa que o erro pode ocupar: do erro − U até o erro + U",
    "Tolerância do plano": "Limites de erro aceitos no plano de calibração do instrumento",
}


class Janela(QMainWindow):
    def __init__(self, servico: Servico | None = None):
        super().__init__()
        self.servico = servico or Servico()
        self.analise: Analise | None = None
        self.linhas: list[LinhaPonto] = []
        self.ocupado = False
        self._tarefa: Tarefa | None = None
        self._pendentes = 0  # correções feitas e ainda não aprendidas pelo modelo
        self.setWindowTitle(f"Leitor de Certificados — v{__version__}")
        self.setAcceptDrops(True)
        self._montar()
        self.avisar("Abra um certificado para começar.", "dica")

    # ================================================================== montagem da tela
    def _montar(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        coluna = QVBoxLayout(raiz)
        coluna.setContentsMargins(12, 8, 12, 8)
        coluna.setSpacing(8)

        # --- faixa 1: título no meio e versão à direita (cinza)
        cabecalho = QHBoxLayout()
        espaco = QLabel("")
        titulo = QLabel("LEITOR DE CERTIFICADOS")
        titulo.setObjectName("titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        versao = QLabel(f"v{__version__}")
        versao.setObjectName("versao")
        versao.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        cabecalho.addWidget(espaco, 1)
        cabecalho.addWidget(titulo, 3)
        cabecalho.addWidget(versao, 1)
        coluna.addLayout(cabecalho)

        # --- faixa 2: botões e andamento
        botoes = QHBoxLayout()
        self.botao_abrir = QPushButton("Abrir certificado")
        self.botao_abrir.setObjectName("principal")  # a ação principal: o único botão vermelho
        self.botao_abrir.clicked.connect(self.escolher_certificado)
        self.botao_corrigir = QPushButton("Corrigir")
        self.botao_corrigir.setCheckable(True)
        self.botao_corrigir.setToolTip(
            "Liga o modo de correção: clique numa palavra (ou arraste um retângulo sobre várias) "
            "e escolha o que ela é.")
        self.botao_corrigir.toggled.connect(self.alternar_correcao)
        self.botao_aprender = QPushButton("Aprender com as correções")
        self.botao_aprender.setToolTip(
            "Treina o modelo de novo com os certificados fictícios e com os reais que você "
            "corrigiu (os reais pesam 5 vezes mais), e confere o certificado aberto outra vez.")
        self.botao_aprender.clicked.connect(self.aprender)
        botoes.addWidget(self.botao_abrir)
        botoes.addWidget(self.botao_corrigir)
        botoes.addWidget(self.botao_aprender)
        botoes.addSpacing(16)
        self.andamento = QLabel("")
        self.andamento.setObjectName("dica")
        self.barra = QProgressBar()
        self.barra.setRange(0, 0)  # animação sem fim: não sabemos quanto falta
        self.barra.setFixedWidth(180)
        self.barra.setTextVisible(False)
        self.barra.hide()
        botoes.addWidget(self.andamento, 1)
        botoes.addWidget(self.barra)
        coluna.addLayout(botoes)

        # --- faixa 3: folha à esquerda, painel à direita
        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self._montar_folha())
        divisor.addWidget(self._montar_painel())
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([800, 800])
        coluna.addWidget(divisor, 1)

        # --- faixa 4: área de avisos (nada de pop-up: erros e avisos aparecem aqui)
        self.avisos = QLabel("")
        self.avisos.setObjectName("avisos")
        self.avisos.setWordWrap(True)
        self.avisos.setMinimumHeight(28)
        coluna.addWidget(self.avisos)
        self._atualizar_botoes()

    def _montar_folha(self) -> QGroupBox:
        caixa = QGroupBox("Folha")
        lay = QVBoxLayout(caixa)
        topo = QHBoxLayout()
        self.dica_folha = QLabel("")
        self.dica_folha.setObjectName("dica")
        topo.addWidget(self.dica_folha, 1)
        for texto, dica, acao in (("−", "Diminuir a folha", lambda: self.folha.zoom(1 / 1.25)),
                                  ("+", "Aumentar a folha", lambda: self.folha.zoom(1.25)),
                                  ("Ajustar", "Cabe a largura da folha na tela",
                                   lambda: self.folha.ajustar())):
            botao = QPushButton(texto)
            botao.setObjectName("zoom")
            botao.setToolTip(dica)
            botao.clicked.connect(acao)
            topo.addWidget(botao)
        lay.addLayout(topo)
        self.folha = FolhaView()
        self.folha.palavras_escolhidas.connect(self.escolher_rotulo)
        lay.addWidget(self.folha, 1)
        return caixa

    def _montar_painel(self) -> QWidget:
        painel = QWidget()
        lay = QVBoxLayout(painel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        parecer = QGroupBox("Parecer")
        play = QVBoxLayout(parecer)
        self.parecer = QLabel("—")
        self.parecer.setObjectName("parecer")
        self.parecer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        play.addWidget(self.parecer)
        self.motivo = QLabel("")
        self.motivo.setWordWrap(True)
        self.motivo.setTextFormat(Qt.TextFormat.PlainText)
        self.motivo.hide()
        play.addWidget(self.motivo)
        lay.addWidget(parecer)

        instrumento = QGroupBox("Instrumento")
        grade = QGridLayout(instrumento)
        self.campos: dict[str, QLabel] = {}
        for linha, (chave, nome, dica) in enumerate((
            ("codigo", "Código achado", "O código do instrumento lido no certificado"),
            ("plano", "Instrumento / plano", "Nome do plano no cadastro do sistema de calibração"),
            ("faixa", "Faixa lida", "Faixa de utilização que o modelo leu no certificado"),
            ("faixa_cadastro", "Faixa no cadastro",
             "Só informação: a conferência ainda NÃO compara a faixa com o cadastro"),
            ("tipo", "Tipo lido", "Tipo de instrumento que o modelo leu no certificado"),
        )):
            rotulo = QLabel(nome + ":")
            rotulo.setToolTip(dica)
            valor = QLabel("—")
            valor.setWordWrap(True)
            valor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grade.addWidget(rotulo, linha, 0, Qt.AlignmentFlag.AlignTop)
            grade.addWidget(valor, linha, 1)
            self.campos[chave] = valor
        grade.setColumnStretch(1, 1)
        lay.addWidget(instrumento)

        pontos = QGroupBox("Pontos conferidos")
        tlay = QVBoxLayout(pontos)
        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        for n, nome in enumerate(COLUNAS):
            if nome in DICAS_COLUNAS:
                self.tabela.horizontalHeaderItem(n).setToolTip(DICAS_COLUNAS[nome])
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # só consulta
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.verticalHeader().hide()
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(COLUNAS.index("Tolerância do plano"),
                                 QHeaderView.ResizeMode.Stretch)
        self.tabela.setStyleSheet("QTableWidget { font-size: 11pt; } "
                                  "QHeaderView::section { font-size: 11pt; }")
        tlay.addWidget(self.tabela)
        lay.addWidget(pontos, 1)
        return painel

    # ================================================================== avisos e andamento
    def avisar(self, texto: str, tipo: str = "info") -> None:
        """Mensagem na área de avisos. Amarelo = aviso, vermelho = erro, cinza = dica."""
        cor = {"aviso": AMARELO, "erro": VERMELHO_TEXTO, "dica": DICA}.get(tipo, "#f0f0f0")
        estilo = "font-style: italic;" if tipo == "dica" else ""
        self.avisos.setStyleSheet(f"color: {cor}; {estilo}")
        self.avisos.setText(texto)

    def _ocupar(self, texto: str) -> None:
        self.ocupado = True
        self.andamento.setText(texto)
        self.barra.show()
        self._atualizar_botoes()

    def _liberar(self) -> None:
        self.ocupado = False
        self.andamento.setText("")
        self.barra.hide()
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        livre = not self.ocupado
        self.botao_abrir.setEnabled(livre)
        self.botao_corrigir.setEnabled(livre and self.analise is not None)
        self.botao_aprender.setEnabled(livre)
        self.botao_aprender.setText(
            f"Aprender com as correções ({self._pendentes})" if self._pendentes
            else "Aprender com as correções")

    def _rodar(self, funcao, ao_concluir, texto: str) -> None:
        """Roda `funcao(progresso)` em segundo plano; `ao_concluir(resultado)` volta na tela."""
        self._ocupar(texto)
        tarefa = Tarefa(funcao, self)
        tarefa.progresso.connect(self.andamento.setText)
        tarefa.concluida.connect(lambda r: self._terminou(ao_concluir, r))
        tarefa.falhou.connect(self._falhou)
        self._tarefa = tarefa  # guardada: sem isso o Python apagaria a thread no meio do trabalho
        tarefa.start()

    def _terminou(self, ao_concluir, resultado) -> None:
        self._liberar()
        ao_concluir(resultado)

    def _falhou(self, erro: str) -> None:
        self._liberar()
        self.folha.parar_brilho()
        self.avisar(f"Algo deu errado: {erro}", "erro")

    # ================================================================== modelo
    def iniciar(self) -> None:
        """Prepara o modelo ao abrir: usa o salvo ou treina o base (pode demorar)."""
        if self.servico.pastas.modelo.exists():
            texto = "Abrindo o modelo salvo"
        else:
            texto = "Treinando o modelo pela primeira vez"
            self.avisar("Primeira vez neste computador: o modelo base está sendo treinado e "
                        "isso pode levar alguns minutos. Depois ele fica salvo.", "aviso")
        self._rodar(self.servico.preparar_modelo, self._modelo_pronto, texto)

    def _modelo_pronto(self, origem: str) -> None:
        self.avisar("Modelo pronto (" + ("salvo" if origem == "salvo" else "recém-treinado")
                    + "). Abra um certificado.", "dica")

    def aprender(self) -> None:
        if self.ocupado:
            return
        self._rodar(self.servico.aprender, self._aprendeu, "Aprendendo com as correções")

    def _aprendeu(self, reais: int) -> None:
        self._pendentes = 0
        self._atualizar_botoes()
        self.avisar(f"O modelo aprendeu com {reais} certificado(s) real(is) corrigido(s) e foi "
                    "salvo.", "info")
        if self.analise is not None:
            self.abrir(self.analise.caminho)  # confere o mesmo certificado com o modelo novo

    # ================================================================== abrir e analisar
    def escolher_certificado(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher o certificado", "", "Certificados (*.pdf)")
        if caminho:
            self.abrir(Path(caminho))

    def abrir(self, caminho: Path) -> None:
        if self.ocupado:
            self.avisar("Espere o trabalho atual terminar.", "aviso")
            return
        if self.servico.modelo is None:
            self.avisar("O modelo ainda não está pronto.", "aviso")
            return
        try:
            # a folha aparece já, enquanto a análise (OCR) roda em segundo plano
            previa = renderizar_folha(caminho, 0, escala=1.5)
        except Exception as erro:
            self.avisar(f"Não consegui abrir {Path(caminho).name}: {erro}", "erro")
            return
        self.analise = None
        self.botao_corrigir.setChecked(False)
        self._limpar_painel()
        self.folha.mostrar_imagem(previa)
        self.folha.iniciar_brilho()
        self.dica_folha.setText(Path(caminho).name)
        self.avisar("Analisando…", "dica")
        self._rodar(lambda progresso: self.servico.analisar(caminho, progresso),
                    self.mostrar_analise, "Analisando o certificado")

    def mostrar_analise(self, analise: Analise) -> None:
        self.analise = analise
        self.linhas = descrever_pontos(analise.conferencia)
        self.folha.parar_brilho()
        self.folha.mostrar_analise(analise, self.linhas)
        self.dica_folha.setText(
            f"{analise.caminho.name} — {analise.pagina.origem}, "
            f"{len(analise.pagina.palavras)} palavras. Passe o mouse num ponto para ver a conta.")
        self._preencher_painel(analise)
        self._atualizar_botoes()
        self.avisar("Pronto. Se o modelo errou algo, ligue o botão Corrigir.", "dica")

    # ================================================================== painel da direita
    def _limpar_painel(self) -> None:
        self.parecer.setText("—")
        self.parecer.setStyleSheet(f"background: {CAMPO}; color: {DICA};")
        self.motivo.setText("")
        self.motivo.hide()
        for valor in self.campos.values():
            valor.setText("—")
        self.tabela.setRowCount(0)

    def _preencher_painel(self, analise: Analise) -> None:
        conferencia = analise.conferencia
        resultado = conferencia.resultado if conferencia else Resultado.PENDENTE
        estilos = {
            Resultado.APROVADO: (FAIXA_DENTRO, "#ffffff", "APROVADO"),
            Resultado.REPROVADO: (FAIXA_FORA, "#ffffff", "REPROVADO"),
        }
        fundo, letra, texto = estilos.get(resultado, (AMARELO, "#000000", "PENDENTE"))
        self.parecer.setText(texto)
        self.parecer.setStyleSheet(f"background: {fundo}; color: {letra};")
        motivos = list(analise.avisos) + (list(conferencia.avisos) if conferencia else [])
        for p in (conferencia.pontos if conferencia else []):
            motivos += [f"ponto {p.lido.nominal:g}: {a}" for a in p.avisos]
        if resultado == Resultado.PENDENTE or resultado == Resultado.REPROVADO:
            self.motivo.setText("\n".join(f"• {m}" for m in motivos))
        else:
            self.motivo.setText("")
        self.motivo.setStyleSheet(f"color: {AMARELO};")
        self.motivo.setVisible(bool(self.motivo.text()))  # sem texto, não ocupa lugar
        self.campos["codigo"].setText(
            (conferencia.codigo if conferencia and conferencia.codigo else None)
            or analise.campos.get("codigo") or "não encontrado")
        self.campos["plano"].setText(
            (conferencia.plano_nome if conferencia and conferencia.plano_nome else None)
            or "sem plano no cadastro")
        self.campos["faixa"].setText(analise.campos.get("faixa") or "não encontrada")
        self.campos["faixa_cadastro"].setText(analise.faixa_cadastro or "—")
        self.campos["tipo"].setText(analise.campos.get("tipo") or "não encontrado")
        self._preencher_tabela()

    def _preencher_tabela(self) -> None:
        self.tabela.setRowCount(len(self.linhas))
        for r, linha in enumerate(self.linhas):
            valores = [linha.nominal, linha.encontrado, linha.erro, linha.incerteza,
                       linha.erro_mais_u, linha.tolerancia, linha.resultado.value]
            for c, valor in enumerate(valores):
                celula = QTableWidgetItem(valor)
                celula.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                celula.setToolTip(linha.dica())
                if c == len(valores) - 1:
                    self._pintar_resultado(celula, linha.resultado)
                self.tabela.setItem(r, c, celula)

    @staticmethod
    def _pintar_resultado(celula: QTableWidgetItem, resultado: Resultado) -> None:
        fonte = QFont(celula.font())
        fonte.setBold(True)
        celula.setFont(fonte)
        if resultado == Resultado.APROVADO:
            celula.setForeground(QBrush(QColor(VERDE)))
        elif resultado == Resultado.REPROVADO:
            celula.setForeground(QBrush(QColor(VERMELHO_TEXTO)))
        else:  # "não avaliado" e parecidos: aviso amarelo com letra preta
            celula.setBackground(QBrush(QColor(AMARELO)))
            celula.setForeground(QBrush(QColor("#000000")))

    # ================================================================== corrigir
    def alternar_correcao(self, ligado: bool) -> None:
        self.folha.set_modo_corrigir(ligado)
        if ligado:
            self.avisar("Modo Corrigir: clique numa palavra, ou arraste um retângulo sobre várias, "
                        "e escolha o que elas são. As palavras “outro” aparecem em cinza.",
                        "aviso")
        elif self.analise is not None:
            self.avisar("Modo Corrigir desligado.", "dica")

    def escolher_rotulo(self, indices: list[int], posicao: QPoint) -> None:
        """Abre a lista de rótulos onde o mouse soltou e grava a escolha."""
        if self.analise is None:
            return
        menu = QMenu(self)
        for rotulo, nome in ROTULOS.items():
            acao = menu.addAction(nome)
            acao.setData(rotulo)
        escolhida = menu.exec(posicao)
        if escolhida is None:
            self.folha.limpar_selecao()
            return
        self.aplicar_rotulo(indices, escolhida.data())

    def aplicar_rotulo(self, indices: list[int], rotulo: str) -> None:
        try:
            mudaram = gravar_correcao(self.servico.pastas, self.analise, indices, rotulo)
        except Exception as erro:
            self.avisar(f"Não consegui gravar a correção: {erro}", "erro")
            return
        self.folha.limpar_selecao()  # repinta com os rótulos novos
        if mudaram:
            self._pendentes += mudaram
            self._atualizar_botoes()
        self.avisar(
            f"{len(indices)} palavra(s) marcada(s) como “{ROTULOS[rotulo]}”. "
            "Quando terminar, clique em Aprender com as correções.", "info")

    # ================================================================== arrastar e soltar
    def dragEnterEvent(self, evento: QDragEnterEvent) -> None:
        urls = evento.mimeData().urls()
        if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".pdf"):
            evento.acceptProposedAction()

    def dropEvent(self, evento: QDropEvent) -> None:
        self.abrir(Path(evento.mimeData().urls()[0].toLocalFile()))

    def closeEvent(self, evento) -> None:
        # espera o trabalho em segundo plano acabar, para não derrubar uma thread no meio
        if self._tarefa is not None and self._tarefa.isRunning():
            self._tarefa.wait(15000)
        super().closeEvent(evento)
