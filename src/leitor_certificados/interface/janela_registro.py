"""Janelinha do registro das análises (ícone do relógio no canto de cima).

Duas abas: "Registro" (o que foi registrado) e "Lixeira" (o que foi apagado). Daqui se manda
para a Lixeira, restaura, apaga de vez e abre tudo numa planilha (.xlsx).
"""

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..registro import Registro, RegistroAnalises
from .estilo import cor

COLUNAS = ["Nº", "Data e hora", "Usuário", "Certificado", "Código", "Parecer", "Correções"]


class PerguntaAprovacao(QDialog):
    """Pede o nome, o RE e a data de quem aprova. Nome e RE vêm preenchidos com os da última
    aprovação feita neste usuário do Windows."""

    def __init__(self, certificado: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aprovar certificado")
        self._preferencias = QSettings("LeitorCertificadosIA", "aprovacao")
        coluna = QVBoxLayout(self)
        explica = QLabel(f"Aprovar de vez o certificado {certificado}.\n"
                         "O registro passa a constar APROVADO e o PDF recebe o carimbo.")
        explica.setWordWrap(True)
        coluna.addWidget(explica)
        formulario = QFormLayout()
        self.nome = QLineEdit(str(self._preferencias.value("nome", "")))
        self.nome.setPlaceholderText("Nome do responsável")
        self.re = QLineEdit(str(self._preferencias.value("re", "")))
        self.re.setPlaceholderText("Matrícula")
        self.data = QDateEdit(QDate.currentDate())
        self.data.setCalendarPopup(True)  # calendário no lugar da setinha
        self.data.setDisplayFormat("dd/MM/yyyy")
        formulario.addRow("Nome do responsável", self.nome)
        formulario.addRow("RE", self.re)
        formulario.addRow("Data da aprovação", self.data)
        coluna.addLayout(formulario)
        self.erro = QLabel("")
        self.erro.setStyleSheet(f"color: {cor('erro_texto')};")
        self.erro.hide()
        coluna.addWidget(self.erro)
        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        aprovar = QPushButton("Aprovar")
        aprovar.setObjectName("principal")  # a ação principal desta caixinha
        cancelar.clicked.connect(self.reject)
        aprovar.clicked.connect(self._conferir)
        botoes.addWidget(cancelar)
        botoes.addWidget(aprovar)
        coluna.addLayout(botoes)

    def valores(self) -> tuple[str, str, str]:
        return (self.nome.text().strip(), self.re.text().strip(),
                self.data.date().toString("dd/MM/yyyy"))

    def _conferir(self) -> None:
        nome, re, _ = self.valores()
        if not nome or not re:
            self.erro.setText("Preencha o nome e o RE de quem aprova.")
            self.erro.show()
            return
        self._preferencias.setValue("nome", nome)
        self._preferencias.setValue("re", re)
        self.accept()


def _data_br(data_hora: str) -> str:
    """'2026-11-17 14:30:05' → '17/11/2026 14:30'."""
    try:
        data, hora = data_hora.split(" ")
        ano, mes, dia = data.split("-")
        return f"{dia}/{mes}/{ano} {hora[:5]}"
    except ValueError:
        return data_hora


def detalhes(r: Registro) -> str:
    """Texto da linha escolhida, embaixo da tabela."""
    partes = [f"Nº {r.id} — {r.certificado}",
              f"Registrado em {_data_br(r.data_hora)} por {r.usuario} ({r.pc})",
              f"Plano: {r.plano or '—'}    Parecer da IA: {r.parecer or '—'}",
              f"Palavras corrigidas: {r.correcoes}    Textos corrigidos: {r.textos}"]
    if r.aprovado:
        partes.insert(3, f"APROVADO por {r.aprovado_por} (RE {r.aprovado_re}) em "
                         f"{r.aprovado_data} — clicado em {_data_br(r.aprovado_em)} por "
                         f"{r.aprovado_usuario} ({r.aprovado_pc})")
    if r.manual:
        partes.append("Digitado à mão: " + "; ".join(f"{k}: {v}" for k, v in r.manual.items()))
    partes += [f"Problema: {e}" for e in r.motivos.get("erros", [])]
    partes += [f"Aviso: {a}" for a in r.motivos.get("avisos", [])]
    if r.na_lixeira_em:
        partes.append(f"Na Lixeira desde {_data_br(r.na_lixeira_em)}")
    partes.append(f"Programa {r.versao_programa}, modelo {r.versao_modelo}")
    return "\n".join(partes)


class _Aba(QWidget):
    """Uma tabela de registros + os detalhes da linha escolhida."""

    def __init__(self, registro: RegistroAnalises, lixeira: bool):
        super().__init__()
        self.registro = registro
        self.lixeira = lixeira
        self.itens: list[Registro] = []
        coluna = QVBoxLayout(self)
        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.verticalHeader().hide()
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setCursor(Qt.CursorShape.PointingHandCursor)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(COLUNAS.index("Certificado"), QHeaderView.ResizeMode.Stretch)
        # o clique (não a mudança de seleção) mostra os detalhes, mesmo na linha já escolhida
        self.tabela.cellClicked.connect(lambda *_: self._mostrar_detalhes())
        self.tabela.itemSelectionChanged.connect(self._mostrar_detalhes)
        self.detalhe = QLabel("")
        self.detalhe.setObjectName("dica")
        self.detalhe.setWordWrap(True)
        self.detalhe.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        coluna.addWidget(self.tabela, 1)
        coluna.addWidget(self.detalhe)
        self.recarregar()

    def recarregar(self) -> None:
        self.itens = self.registro.listar(self.lixeira)
        self.tabela.setRowCount(len(self.itens))
        for n, r in enumerate(self.itens):
            valores = [str(r.id), _data_br(r.data_hora), r.usuario, r.certificado,
                       r.codigo or "—", r.parecer_final or "—",
                       str(r.correcoes + r.textos)]
            for c, valor in enumerate(valores):
                celula = QTableWidgetItem(valor)
                celula.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabela.setItem(n, c, celula)
        self._mostrar_detalhes()

    def escolhido(self) -> Registro | None:
        linha = self.tabela.currentRow()
        if not self.tabela.selectedItems() or not 0 <= linha < len(self.itens):
            return None
        return self.itens[linha]

    def _mostrar_detalhes(self) -> None:
        r = self.escolhido()
        if r is not None:
            self.detalhe.setText(detalhes(r))
        elif not self.itens:
            self.detalhe.setText("A Lixeira está vazia." if self.lixeira
                                 else "Nenhuma análise registrada ainda.")
        else:
            self.detalhe.setText("Clique numa linha para ver os detalhes.")
        self.detalhe.setVisible(bool(self.detalhe.text()))
        self.mudou_escolha()

    def mudou_escolha(self) -> None:  # trocado pela janela, para ligar/desligar os botões
        pass


class JanelaRegistro(QDialog):
    def __init__(self, registro: RegistroAnalises, parent=None, servico=None):
        super().__init__(parent)
        self.setWindowTitle("Registro das análises")
        self.registro = registro
        self.servico = servico  # aprovar e achar os PDFs guardados (sem ele, só a lista)
        self.mexeu = False  # algo foi para a Lixeira, voltou ou foi apagado (muda o treino)
        coluna = QVBoxLayout(self)
        self.abas = QTabWidget()
        self.aba_registro = _Aba(registro, lixeira=False)
        self.aba_lixeira = _Aba(registro, lixeira=True)
        self.abas.addTab(self.aba_registro, "Registro")
        self.abas.addTab(self.aba_lixeira, "Lixeira")
        coluna.addWidget(self.abas, 1)

        botoes = QHBoxLayout()
        self.botao_lixeira = QPushButton("Mandar para a Lixeira")
        self.botao_restaurar = QPushButton("Restaurar")
        self.botao_apagar = QPushButton("Apagar de vez")
        self.botao_aprovar = QPushButton("Aprovar")
        self.botao_aprovar.setToolTip(
            "Aprovação final pelo responsável: vale mesmo se a IA deu pendente ou reprovado. "
            "Pede nome, RE e data, e carimba o PDF.")
        self.botao_desaprovar = QPushButton("Apagar aprovação")
        self.botao_pdf = QPushButton("Abrir PDF")
        self.botao_pdf.setToolTip("O certificado com os checks da conferência (e o carimbo, "
                                  "se foi aprovado)")
        self.botao_aprovar.clicked.connect(self.aprovar)
        self.botao_desaprovar.clicked.connect(self.apagar_aprovacao)
        self.botao_pdf.clicked.connect(self.abrir_pdf)
        self.botao_planilha = QPushButton("Abrir em planilha")
        self.botao_fechar = QPushButton("Fechar")
        self.botao_lixeira.clicked.connect(self.mandar_para_lixeira)
        self.botao_restaurar.clicked.connect(self.restaurar)
        self.botao_apagar.clicked.connect(self.apagar_de_vez)
        self.botao_planilha.clicked.connect(self.abrir_planilha)
        self.botao_fechar.clicked.connect(self.accept)
        for b in (self.botao_aprovar, self.botao_desaprovar, self.botao_pdf,
                  self.botao_lixeira, self.botao_restaurar, self.botao_apagar):
            botoes.addWidget(b)
        botoes.addStretch(1)
        botoes.addWidget(self.botao_planilha)
        botoes.addWidget(self.botao_fechar)
        coluna.addLayout(botoes)

        self.aviso = QLabel("")
        self.aviso.setWordWrap(True)
        self.aviso.hide()
        coluna.addWidget(self.aviso)

        self.aba_registro.mudou_escolha = self._atualizar_botoes
        self.aba_lixeira.mudou_escolha = self._atualizar_botoes
        self.abas.currentChanged.connect(lambda _: self._atualizar_botoes())
        self._atualizar_botoes()
        self.resize(1100, 650)

    # ------------------------------------------------------------------ estado
    def _aba(self) -> _Aba:
        return self.abas.currentWidget()

    def _atualizar_botoes(self) -> None:
        if not hasattr(self, "botao_fechar"):
            return  # ainda montando
        na_lixeira = self._aba() is self.aba_lixeira
        r = self._aba().escolhido()
        tem = r is not None
        aprovado = tem and r.aprovado
        self.botao_aprovar.setVisible(not na_lixeira and self.servico is not None
                                      and not aprovado)
        self.botao_aprovar.setEnabled(tem)
        self.botao_desaprovar.setVisible(not na_lixeira and self.servico is not None
                                         and aprovado)
        self.botao_pdf.setVisible(self.servico is not None)
        self.botao_pdf.setEnabled(tem)
        self.botao_lixeira.setVisible(not na_lixeira)
        self.botao_restaurar.setVisible(na_lixeira)
        self.botao_apagar.setVisible(na_lixeira)
        for b in (self.botao_lixeira, self.botao_restaurar, self.botao_apagar):
            b.setEnabled(tem)

    def _recarregar(self, mexeu_no_treino: bool = True) -> None:
        linha = self._aba().tabela.currentRow()
        self.mexeu = self.mexeu or mexeu_no_treino
        self.aba_registro.recarregar()
        self.aba_lixeira.recarregar()
        if not mexeu_no_treino and 0 <= linha < self._aba().tabela.rowCount():
            self._aba().tabela.selectRow(linha)  # continua na mesma linha
        self._atualizar_botoes()

    def _confirmar(self, titulo: str, texto: str) -> bool:
        caixa = QMessageBox(QMessageBox.Icon.Warning, titulo, texto, parent=self)
        sim = caixa.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        caixa.addButton("Não", QMessageBox.ButtonRole.NoRole)
        caixa.exec()
        return caixa.clickedButton() is sim

    # ------------------------------------------------------------------ ações
    def aprovar(self) -> None:
        r = self._aba().escolhido()
        if r is None or self.servico is None:
            return
        pergunta = PerguntaAprovacao(r.certificado, self)
        if pergunta.exec() != QDialog.DialogCode.Accepted:
            return
        self.aprovar_com(*pergunta.valores())

    def aprovar_com(self, nome: str, re: str, data: str) -> None:
        r = self._aba().escolhido()
        if r is None:
            return
        try:
            self.servico.aprovar(r.id, nome, re, data)
        except Exception as erro:
            self._avisar(f"Não consegui aprovar: {erro}")
            return
        self._recarregar(mexeu_no_treino=False)

    def apagar_aprovacao(self) -> None:
        r = self._aba().escolhido()
        if r is None or not self._confirmar(
                "Apagar aprovação",
                f"A aprovação do registro nº {r.id} ({r.certificado}) será apagada, junto com "
                "o PDF carimbado. Tem certeza?"):
            return
        self.servico.apagar_aprovacao(r.id)
        self._recarregar(mexeu_no_treino=False)

    def abrir_pdf(self) -> None:
        r = self._aba().escolhido()
        if r is None:
            return
        arquivo = (self.servico.arquivo_do_registro(r.arquivo_aprovado)
                   or self.servico.arquivo_do_registro(r.arquivo_conferido))
        if arquivo is None:
            self._avisar("Este registro é de antes da cópia com os checks existir: abra o "
                         "certificado e registre de novo.")
            return
        try:
            os.startfile(arquivo)  # noqa: S606 — abre no leitor de PDF do Windows
        except Exception as erro:
            self._avisar(f"Não consegui abrir o PDF: {erro}")

    def mandar_para_lixeira(self) -> None:
        r = self._aba().escolhido()
        if r is None or not self._confirmar(
                "Mandar para a Lixeira",
                "Apagar pode tirar esse aprendizado. Tem certeza?\n\n"
                "(Fica na Lixeira: dá para restaurar depois.)"):
            return
        self.registro.mandar_para_lixeira(r.id)
        self._recarregar()

    def restaurar(self) -> None:
        r = self._aba().escolhido()
        if r is None:
            return
        self.registro.restaurar(r.id)
        self._recarregar()

    def apagar_de_vez(self) -> None:
        r = self._aba().escolhido()
        if r is None or not self._confirmar(
                "Apagar de vez",
                f"O registro nº {r.id} ({r.certificado}) será apagado para sempre e não "
                "dá para voltar atrás. Tem certeza?"):
            return
        self.registro.apagar_de_vez(r.id)
        self._recarregar()

    def abrir_planilha(self) -> None:
        """Gera a planilha numa pasta temporária e abre no Excel (é só uma cópia para ler)."""
        destino = Path(tempfile.gettempdir()) / "registro_das_analises.xlsx"
        try:
            self.registro.exportar_planilha(destino)
            os.startfile(destino)  # noqa: S606 — abre no programa padrão do Windows
        except PermissionError:
            self._avisar("A planilha anterior ainda está aberta no Excel: feche-a e tente de "
                         "novo.")
        except Exception as erro:
            self._avisar(f"Não consegui abrir a planilha: {erro}")

    def _avisar(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.setStyleSheet(f"color: {cor('erro_texto')};")
        self.aviso.show()
