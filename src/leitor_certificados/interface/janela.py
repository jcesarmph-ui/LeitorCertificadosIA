"""A janela principal: botões em cima, a folha à esquerda, o parecer e os pontos à direita.

A janela só mostra e chama o `servico`. Nada de regra de negócio aqui: quem lê, confere, corrige
e treina é o `servico` (e os módulos de leitura, aprendizado e conferência por baixo dele).
Tudo o que demora roda numa `Tarefa` (thread), para a tela nunca travar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..conferencia.avaliacao import Resultado
from ..conferencia.cadastro import CAMPOS as CAMPOS_CADASTRO
from ..conferencia.cadastro import Bate, ItemComparado, comparar_com_cadastro
from .estilo import (
    AMARELO,
    FAIXA_DENTRO,
    FAIXA_FORA,
    VERDE,
    cor,
)
from .folha import FolhaView, tipo_do_rotulo
from .legenda import icone_do_rotulo
from .quadro import QuadroPonto
from .servico import (
    CAMPOS_MANUAIS,
    ROTULOS,
    Analise,
    LinhaPonto,
    Servico,
    descrever_pontos,
    gravar_correcao,
    gravar_manual,
    gravar_texto,
    renderizar_folha,
)
from .tarefas import Tarefa

COLUNAS = ["Nominal", "Encontrado", "Erro", "U", "Erro ± U", "Tolerância", "Critério",
           "Resultado"]
DICAS_COLUNAS = {
    "U": "Incerteza expandida de medição, informada no certificado",
    "Erro ± U": "O erro somado à incerteza, do lado mais perto da tolerância (igual ao "
                "programa de calibração). Ex.: erro −1 e U 1 → −2. \"± U\" só quando o erro é 0",
    "Tolerância": "Tolerância do plano: limites de erro aceitos no plano de calibração",
    "Critério": "Critério de aceitação ± informado no certificado. Se for diferente da "
                "tolerância do plano, fica amarelo (não muda o parecer)",
}


class Janela(QMainWindow):
    def __init__(self, servico: Servico | None = None):
        super().__init__()
        self.servico = servico or Servico()
        self.analise: Analise | None = None
        self.linhas: list[LinhaPonto] = []
        self.ocupado = False
        self._tarefas: set[Tarefa] = set()  # guardadas: sem isso o Python as apagaria no meio
        self._vez = 0  # muda a cada trabalho novo ou cancelado: resultado de vez antiga é jogado
        self._anterior: Analise | None = None  # para voltar se a análise for cancelada
        self.quadro: QuadroPonto | None = None
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
        self.botao_cancelar = QPushButton("Cancelar análise")
        self.botao_cancelar.setToolTip("Para de esperar esta análise e volta ao que estava antes")
        self.botao_cancelar.clicked.connect(self.cancelar_analise)
        self.botao_cancelar.hide()
        botoes.addWidget(self.andamento, 1)
        botoes.addWidget(self.barra)
        botoes.addWidget(self.botao_cancelar)
        coluna.addLayout(botoes)

        # --- faixa 3: folha à esquerda, painel à direita
        # a largura da folha é calculada para a página A4 caber inteira na altura
        # (`ajustar_divisao`); o resto da largura fica para os painéis da direita
        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        self.caixa_folha = self._montar_folha()
        self.divisor.addWidget(self.caixa_folha)
        self.divisor.addWidget(self._montar_painel())
        self.divisor.setStretchFactor(0, 0)
        self.divisor.setStretchFactor(1, 1)
        coluna.addWidget(self.divisor, 1)

        # --- faixa 4: área de avisos (nada de pop-up: erros e avisos aparecem aqui)
        self.avisos = QLabel("")
        self.avisos.setObjectName("avisos")
        self.avisos.setWordWrap(True)
        self.avisos.setMinimumHeight(28)
        coluna.addWidget(self.avisos)
        self._atualizar_botoes()
        # Mede a tela já agora: sem isso o showMaximized() pode se perder e a janela abrir
        # pequena (o mesmo problema e a mesma solução dos outros programas do usuário).
        self.ensurePolished()
        raiz.layout().activate()

    def _montar_folha(self) -> QGroupBox:
        caixa = QGroupBox("Folha")
        lay = QVBoxLayout(caixa)
        topo = QHBoxLayout()
        self.dica_folha = QLabel("")
        self.dica_folha.setObjectName("dica")
        self.dica_folha.setWordWrap(True)
        # o nome do arquivo nunca alarga a folha: a largura vem da página A4
        self.dica_folha.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        topo.addWidget(self.dica_folha, 1)
        for texto, dica, acao in (("−", "Diminuir a folha", lambda: self.folha.zoom(1 / 1.25)),
                                  ("+", "Aumentar a folha", lambda: self.folha.zoom(1.25)),
                                  ("Ajustar", "A folha inteira na tela",
                                   lambda: self.folha.ajustar())):
            botao = QPushButton(texto)
            botao.setObjectName("zoom")
            botao.setToolTip(dica)
            botao.clicked.connect(acao)
            topo.addWidget(botao)
        self.botao_destacar = QPushButton("Destacar pontos")
        self.botao_destacar.setObjectName("zoom")
        self.botao_destacar.setCheckable(True)
        self.botao_destacar.setChecked(True)
        self.botao_destacar.setToolTip(
            "Ligado: as caixas que não são pontos conferidos ficam mais fracas, para os checks "
            "aparecerem. Ctrl + roda do mouse dá zoom na folha.")
        self.botao_destacar.toggled.connect(lambda ligado: self.folha.set_destacar(ligado))
        topo.insertWidget(1, self.botao_destacar)
        lay.addLayout(topo)

        # digitar à mão (só aparece no modo Corrigir): o que o modelo não conseguiu ler
        # Duas linhas (em cima: qual campo; embaixo: o valor e o botão). Numa linha só, a
        # coluna da folha é estreita e o campo do valor ficava espremido, sem dar para ler.
        self.faixa_manual = QWidget()
        manual = QGridLayout(self.faixa_manual)
        manual.setContentsMargins(0, 0, 0, 0)
        rotulo_manual = QLabel("Digitar à mão:")
        rotulo_manual.setToolTip("Para o que o modelo não conseguiu ler (ex.: código escrito a "
                                 "caneta). A conferência roda de novo na hora com o valor.")
        self.campo_manual = QComboBox()
        for chave, nome in CAMPOS_MANUAIS.items():
            self.campo_manual.addItem(nome, chave)
        self.campo_manual.currentIndexChanged.connect(self._mostrar_valor_manual)
        self.valor_manual = QLineEdit()
        self.valor_manual.setPlaceholderText("Vazio = usar o que o modelo leu")
        self.valor_manual.returnPressed.connect(self.usar_valor_manual)
        botao_manual = QPushButton("Usar valor")
        botao_manual.clicked.connect(self.usar_valor_manual)
        manual.addWidget(rotulo_manual, 0, 0)
        manual.addWidget(self.campo_manual, 0, 1, 1, 2)
        manual.addWidget(self.valor_manual, 1, 0, 1, 2)
        manual.addWidget(botao_manual, 1, 2)
        manual.setColumnStretch(1, 1)
        self.faixa_manual.hide()
        lay.addWidget(self.faixa_manual)

        self.folha = FolhaView()
        self.folha.palavras_escolhidas.connect(self.escolher_rotulo)
        self.folha.ponto_clicado.connect(self.abrir_quadro)
        self.folha.palavra_clicada.connect(lambda i, onde: self.abrir_quadro(-1, onde, i))
        self.folha.texto_corrigido.connect(self.corrigir_texto)
        # a altura da folha só fica certa depois que o Qt mede tudo: recalcula a largura a cada
        # mudança (para quando a largura já está certa, então não fica num vaivém)
        self.folha.redimensionada.connect(lambda: QTimer.singleShot(0, self.ajustar_divisao))
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

        # Comparador: o que o cadastro diz × o que foi lido no certificado (pedido do usuário,
        # 2026-11-13). Check verde = bate; amarelo = não bate. Só informa: não muda o parecer.
        instrumento = QGroupBox("Instrumento")
        grade = QGridLayout(instrumento)
        grade.setHorizontalSpacing(14)
        plano_rotulo = QLabel("Plano:")
        plano_rotulo.setToolTip("Nome do plano no cadastro do sistema de calibração")
        self.campos: dict[str, QLabel] = {}  # o que foi lido no certificado (e "plano")
        self.campos_cadastro: dict[str, QLabel] = {}  # o que o cadastro diz
        self.marcas: dict[str, QLabel] = {}  # ✓ bate / não bate
        self.campos["plano"] = QLabel("—")
        grade.addWidget(plano_rotulo, 0, 0)
        grade.addWidget(self.campos["plano"], 0, 1, 1, 3)
        for coluna, (titulo, dica) in enumerate((
            ("Cadastro", "O que o cadastro do instrumento diz (sistema de calibração)"),
            ("Certificado", "O que o modelo leu no certificado"),
        ), start=1):
            cabeca = QLabel(titulo)
            cabeca.setStyleSheet("font-weight: bold;")
            cabeca.setToolTip(dica)
            grade.addWidget(cabeca, 1, coluna)
        for linha, (chave, nome) in enumerate(CAMPOS_CADASTRO, start=2):
            rotulo = QLabel(nome + ":")
            grade.addWidget(rotulo, linha, 0, Qt.AlignmentFlag.AlignTop)
            for destino, coluna in ((self.campos_cadastro, 1), (self.campos, 2)):
                valor = QLabel("—")
                valor.setWordWrap(True)
                valor.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                grade.addWidget(valor, linha, coluna)
                destino[chave] = valor
            marca = QLabel("")
            marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grade.addWidget(marca, linha, 3)
            self.marcas[chave] = marca
        grade.setColumnStretch(1, 1)
        grade.setColumnStretch(2, 1)
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
        cab.setSectionResizeMode(COLUNAS.index("Tolerância"),
                                 QHeaderView.ResizeMode.Stretch)
        self.tabela.setStyleSheet("QTableWidget { font-size: 11pt; } "
                                  "QHeaderView::section { font-size: 11pt; }")
        tlay.addWidget(self.tabela)
        lay.addWidget(pontos, 1)
        return painel

    # ================================================================== avisos e andamento
    def avisar(self, texto: str, tipo: str = "info") -> None:
        """Mensagem na área de avisos. Amarelo = aviso, vermelho = erro, cinza = dica."""
        tinta = {"aviso": cor("aviso_texto"), "erro": cor("erro_texto"),
                 "dica": cor("dica")}.get(tipo, cor("texto"))
        estilo = "font-style: italic;" if tipo == "dica" else ""
        self.avisos.setStyleSheet(f"color: {tinta}; {estilo}")
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
        self.botao_cancelar.hide()
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        livre = not self.ocupado
        self.botao_abrir.setEnabled(livre)
        # depois do primeiro certificado, o botão principal convida a analisar o próximo
        self.botao_abrir.setText("Analisar outro" if self.analise is not None
                                 else "Abrir certificado")
        self.botao_corrigir.setEnabled(livre and self.analise is not None)
        self.botao_aprender.setEnabled(livre)
        self.botao_aprender.setText(
            f"Aprender com as correções ({self._pendentes})" if self._pendentes
            else "Aprender com as correções")

    def _rodar(self, funcao, ao_concluir, texto: str) -> None:
        """Roda `funcao(progresso)` em segundo plano; `ao_concluir(resultado)` volta na tela."""
        self._ocupar(texto)
        self._vez += 1
        vez = self._vez
        tarefa = Tarefa(funcao, self)
        tarefa.progresso.connect(lambda t: self._andamento(vez, t))
        tarefa.concluida.connect(lambda r: self._terminou(vez, ao_concluir, r))
        tarefa.falhou.connect(lambda erro: self._falhou(vez, erro))
        tarefa.finished.connect(lambda: self._tarefas.discard(tarefa))
        self._tarefas.add(tarefa)
        tarefa.start()

    def _andamento(self, vez: int, texto: str) -> None:
        if vez == self._vez:
            self.andamento.setText(texto)

    def _terminou(self, vez: int, ao_concluir, resultado) -> None:
        if vez != self._vez:
            return  # trabalho cancelado: o resultado é jogado fora
        self._liberar()
        ao_concluir(resultado)

    def _falhou(self, vez: int, erro: str) -> None:
        if vez != self._vez:
            return
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
        self._anterior = self.analise
        self.analise = None
        self.botao_corrigir.setChecked(False)
        self._limpar_painel()
        self.folha.mostrar_imagem(previa)
        self.ajustar_divisao()
        self.folha.iniciar_brilho()
        self.dica_folha.setText(Path(caminho).name)
        self.avisar("Analisando…", "dica")
        self._rodar(lambda progresso: self.servico.analisar(caminho, progresso),
                    self.mostrar_analise, "Analisando o certificado")
        self.botao_cancelar.show()

    def cancelar_analise(self) -> None:
        """Volta ao que estava antes. O OCR não dá para interromper no meio: a thread termina
        sozinha em segundo plano e o resultado dela é jogado fora."""
        if not self.ocupado:
            return
        self._vez += 1
        self._liberar()
        self.folha.parar_brilho()
        anterior, self._anterior = self._anterior, None
        if anterior is not None:
            self.mostrar_analise(anterior)
        else:
            self.folha.mostrar_mensagem("Abra um certificado (PDF) ou arraste o arquivo para cá")
            self.dica_folha.setText("")
            self._limpar_painel()
            self._atualizar_botoes()
        self.avisar("Análise cancelada.", "aviso")

    def mostrar_analise(self, analise: Analise) -> None:
        self.analise = analise
        self._anterior = None
        self.linhas = descrever_pontos(analise.conferencia, analise)
        self.folha.parar_brilho()
        self.folha.mostrar_analise(analise, self.linhas)
        self.dica_folha.setText(
            f"{analise.caminho.name} — {analise.pagina.origem}, "
            f"{len(analise.pagina.palavras)} palavras.")
        self.dica_folha.setToolTip(str(analise.caminho))
        self._preencher_painel(analise)
        self._atualizar_botoes()
        self.ajustar_divisao()
        self.avisar("Pronto. Clique num ponto para ver a conta; clique numa palavra para "
                    "corrigir o rótulo; duplo clique corrige o texto.", "dica")

    # ================================================================== painel da direita
    def _limpar_painel(self) -> None:
        self.parecer.setText("—")
        self.parecer.setStyleSheet(f"background: {cor('campo')}; color: {cor('dica')};")
        self.motivo.setText("")
        self.motivo.hide()
        for valor in [*self.campos.values(), *self.campos_cadastro.values()]:
            valor.setText("—")
            valor.setStyleSheet("")
            valor.setToolTip("")
        for marca in self.marcas.values():
            marca.setText("")
            marca.setStyleSheet("")
            marca.setToolTip("")
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
        # avisos sempre aparecem (ex.: faixa diferente do plano avisa mesmo com "Aprovado")
        self.motivo.setText("\n".join(f"• {m}" for m in motivos))
        self.motivo.setStyleSheet(f"color: {cor('aviso_texto')};")
        self.motivo.setVisible(bool(self.motivo.text()))  # sem texto, não ocupa lugar
        self.campos["plano"].setText(
            (conferencia.plano_nome if conferencia and conferencia.plano_nome else None)
            or "sem plano no cadastro")
        # o que foi lido no certificado (o digitado à mão vale mais que o lido)
        lido = {chave: analise.campos.get(chave) or None for chave, _ in CAMPOS_CADASTRO}
        if conferencia and conferencia.codigo:
            lido["codigo"] = conferencia.codigo
        if conferencia and conferencia.faixa_certificado:
            lido["faixa"] = conferencia.faixa_certificado
        digitado = {chave: analise.manual[chave] for chave in ("codigo", "faixa")
                    if analise.manual.get(chave)}
        lido.update(digitado)
        cadastro = conferencia.cadastro if conferencia else {}
        for item in comparar_com_cadastro(cadastro, lido):
            texto = item.certificado or "não encontrado"
            if item.chave in digitado:
                texto += " (digitado)" if item.chave == "codigo" else " (digitada)"
            self.campos[item.chave].setText(texto)
            self.campos_cadastro[item.chave].setText(
                item.cadastro if item.cadastro not in (None, "") else "—")
            self._pintar_marca(item)
        self._preencher_tabela()

    def _pintar_marca(self, item: ItemComparado) -> None:
        """Check verde quando bate; aviso amarelo quando não bate; nada quando falta um lado."""
        marca = self.marcas[item.chave]
        valores = (self.campos[item.chave], self.campos_cadastro[item.chave])
        if item.bate == Bate.SIM:
            marca.setText("✓")
            marca.setStyleSheet(f"color: {VERDE}; font-weight: bold; font-size: 16pt;")
            marca.setToolTip("Cadastro e certificado batem")
            for valor in valores:
                valor.setStyleSheet("font-weight: bold;")
        elif item.bate == Bate.NAO:
            marca.setText("não bate")
            marca.setStyleSheet(f"background: {AMARELO}; color: #000000; font-weight: bold; "
                                "padding: 2px 6px; border-radius: 3px;")
            aviso = (f"{item.nome} do certificado não bate com o cadastro "
                     "(só avisa: não muda o parecer)")
            marca.setToolTip(aviso)
            for valor in valores:
                valor.setStyleSheet(f"color: {cor('aviso_texto')}; font-weight: bold;")
                valor.setToolTip(aviso)
        else:
            marca.setText("")
            marca.setStyleSheet("")
            marca.setToolTip("Falta este dado no cadastro ou no certificado: nada a comparar")
            for valor in valores:
                valor.setStyleSheet("")
                valor.setToolTip("")

    def _preencher_tabela(self) -> None:
        self.tabela.setRowCount(len(self.linhas))
        for r, linha in enumerate(self.linhas):
            valores = [linha.nominal, linha.encontrado, linha.erro, linha.incerteza,
                       linha.erro_mais_u, linha.tolerancia, linha.criterio or "—",
                       linha.resultado.value]
            for c, valor in enumerate(valores):
                celula = QTableWidgetItem(valor)
                celula.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                celula.setToolTip(linha.dica())
                if c == len(valores) - 1:
                    self._pintar_resultado(celula, linha.resultado)
                elif COLUNAS[c] == "Critério" and linha.criterio_diferente:
                    celula.setBackground(QBrush(QColor(AMARELO)))  # aviso: fundo amarelo
                    celula.setForeground(QBrush(QColor("#000000")))
                self.tabela.setItem(r, c, celula)
        # a coluna só aparece quando o laboratório informa o critério (ADR 0009)
        self.tabela.setColumnHidden(COLUNAS.index("Critério"),
                                    not any(linha.criterio for linha in self.linhas))

    @staticmethod
    def _pintar_resultado(celula: QTableWidgetItem, resultado: Resultado) -> None:
        fonte = QFont(celula.font())
        fonte.setBold(True)
        celula.setFont(fonte)
        if resultado == Resultado.APROVADO:
            celula.setForeground(QBrush(QColor(VERDE)))
        elif resultado == Resultado.REPROVADO:
            celula.setForeground(QBrush(QColor(cor("erro_texto"))))
        else:  # "não avaliado" e parecidos: aviso amarelo com letra preta
            celula.setBackground(QBrush(QColor(AMARELO)))
            celula.setForeground(QBrush(QColor("#000000")))

    # ================================================================== corrigir
    def alternar_correcao(self, ligado: bool) -> None:
        self.folha.set_modo_corrigir(ligado)
        self.faixa_manual.setVisible(ligado)
        QTimer.singleShot(0, self.ajustar_divisao)  # a folha ficou mais baixa/alta
        if ligado:
            self._mostrar_valor_manual()
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
            acao = menu.addAction(icone_do_rotulo(rotulo), nome)  # a cor ao lado do nome
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

    def _mostrar_valor_manual(self) -> None:
        campo = self.campo_manual.currentData()
        valor = self.analise.manual.get(campo, "") if self.analise else ""
        self.valor_manual.setText(valor)

    def usar_valor_manual(self) -> None:
        """Grava o valor digitado e confere de novo na hora (só o banco: é rápido)."""
        if self.analise is None:
            return
        campo = self.campo_manual.currentData()
        valor = self.valor_manual.text().strip()
        try:
            gravar_manual(self.servico.pastas, self.analise, campo, valor)
            self.servico.reconferir(self.analise)
        except Exception as erro:
            self.avisar(f"Não consegui usar o valor digitado: {erro}", "erro")
            return
        self.mostrar_analise(self.analise)
        nome = CAMPOS_MANUAIS[campo]
        self.avisar(f"{nome}: usando “{valor}” (digitado)." if valor
                    else f"{nome}: voltou a usar o que o modelo leu.", "info")

    # ================================================================== quadrinho do ponto
    def abrir_quadro(self, n: int, posicao: QPoint, indice: int = -1) -> None:
        """O quadrinho do clique: a conta do ponto `n` (se for um ponto conferido) e/ou a
        pergunta "corrigir?" para a palavra `indice` (se o clique foi numa palavra)."""
        linha = self.linhas[n] if 0 <= n < len(self.linhas) else None
        palavra = None
        if self.analise is not None and 0 <= indice < len(self.analise.rotulos):
            palavra = (indice, self.analise.texto(indice),
                       tipo_do_rotulo(self.analise.rotulos[indice]))
        if linha is None and palavra is None:
            return
        if self.quadro is not None:
            self.quadro.close()
        ordem = None
        if linha is not None:
            # o mesmo ponto fica marcado na folha, na tabela e no título do quadrinho
            self.folha.destacar_ponto(n)
            self.tabela.selectRow(n)
            ordem = (n + 1, len(self.linhas))
            posicao = self.folha.lado_do_ponto(n)  # colado à direita da linha do ponto
        self.quadro = QuadroPonto(linha, self, palavra, ordem)
        self.quadro.destroyed.connect(self._quadro_fechado)
        self.quadro.destroyed.connect(self._selecao_do_quadro_acabou)
        # o quadrinho fecha antes; a lista de rótulos / a caixa de texto abrem logo depois
        self.quadro.corrigir_rotulo.connect(
            lambda i: QTimer.singleShot(0, lambda: self._lista_de_rotulos(i, posicao)))
        self.quadro.corrigir_texto.connect(
            lambda i: QTimer.singleShot(0, lambda: self.folha.abrir_editor(i)))
        self.quadro.abrir_em(posicao)

    def _lista_de_rotulos(self, indice: int, posicao: QPoint) -> None:
        self.folha.selecionar([indice])
        self.escolher_rotulo([indice], posicao)

    def _selecao_do_quadro_acabou(self) -> None:
        if self.folha.editor() is None:
            self.folha.limpar_selecao()

    # ================================================================== corrigir o texto
    def corrigir_texto(self, indice: int, texto: str) -> None:
        """O OCR leu errado: grava o texto certo e confere de novo na hora."""
        if self.analise is None:
            return
        lido = self.analise.pagina.palavras[indice].texto
        try:
            ficou = gravar_texto(self.servico.pastas, self.analise, indice, texto)
            self.servico.recalcular(self.analise)
        except Exception as erro:
            self.avisar(f"Não consegui corrigir o texto: {erro}", "erro")
            return
        self.mostrar_analise(self.analise)
        self.avisar(f"Texto corrigido: lido “{lido}” → “{texto.strip()}”. A conferência foi "
                    "refeita." if ficou else f"Voltou ao texto lido: “{lido}”.", "info")

    # ================================================================== tamanho da folha
    def ajustar_divisao(self) -> None:
        """Largura do painel da folha = a exata para a página caber inteira na altura
        disponível (A4: altura ÷ 1,414), sem sobra dos lados; o resto vai para a direita."""
        total = self.divisor.width()
        altura = self.folha.viewport().height()
        if total <= 0 or altura <= 0:
            return
        sobra = self.caixa_folha.width() - self.folha.viewport().width()  # margens e rolagem
        largura = int(altura / self.folha.razao_da_folha()) + sobra + 6
        largura = max(self.caixa_folha.minimumSizeHint().width(), min(largura, total - 480))
        resto = total - largura - self.divisor.handleWidth()
        if abs(self.divisor.sizes()[0] - largura) > 2:
            self.divisor.setSizes([largura, resto])

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        QTimer.singleShot(0, self.ajustar_divisao)  # depois que o Qt mediu a tela nova

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        QTimer.singleShot(0, self.ajustar_divisao)

    def _quadro_fechado(self) -> None:
        self.quadro = None
        self.folha.destacar_ponto(None)
        self.tabela.clearSelection()

    # ================================================================== arrastar e soltar
    def dragEnterEvent(self, evento: QDragEnterEvent) -> None:
        urls = evento.mimeData().urls()
        if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".pdf"):
            evento.acceptProposedAction()

    def dropEvent(self, evento: QDropEvent) -> None:
        self.abrir(Path(evento.mimeData().urls()[0].toLocalFile()))

    def closeEvent(self, evento) -> None:
        # espera o trabalho em segundo plano acabar, para não derrubar uma thread no meio
        for tarefa in list(self._tarefas):
            if tarefa.isRunning():
                tarefa.wait(15000)
        super().closeEvent(evento)
