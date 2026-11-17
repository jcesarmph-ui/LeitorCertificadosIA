"""Janelinha do registro das análises (ícone do relógio no canto de cima).

Duas abas: "Registro" (o que foi registrado) e "Lixeira" (o que foi apagado). Daqui se manda
para a Lixeira, restaura, apaga de vez e abre tudo numa planilha (.xlsx).
"""

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
              f"Plano: {r.plano or '—'}    Parecer: {r.parecer or '—'}",
              f"Palavras corrigidas: {r.correcoes}    Textos corrigidos: {r.textos}"]
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
                       r.codigo or "—", r.parecer or "—", str(r.correcoes + r.textos)]
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
    def __init__(self, registro: RegistroAnalises, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registro das análises")
        self.registro = registro
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
        self.botao_planilha = QPushButton("Abrir em planilha")
        self.botao_fechar = QPushButton("Fechar")
        self.botao_lixeira.clicked.connect(self.mandar_para_lixeira)
        self.botao_restaurar.clicked.connect(self.restaurar)
        self.botao_apagar.clicked.connect(self.apagar_de_vez)
        self.botao_planilha.clicked.connect(self.abrir_planilha)
        self.botao_fechar.clicked.connect(self.accept)
        for b in (self.botao_lixeira, self.botao_restaurar, self.botao_apagar):
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
        tem = self._aba().escolhido() is not None
        self.botao_lixeira.setVisible(not na_lixeira)
        self.botao_restaurar.setVisible(na_lixeira)
        self.botao_apagar.setVisible(na_lixeira)
        for b in (self.botao_lixeira, self.botao_restaurar, self.botao_apagar):
            b.setEnabled(tem)

    def _recarregar(self) -> None:
        self.mexeu = True
        self.aba_registro.recarregar()
        self.aba_lixeira.recarregar()
        self._atualizar_botoes()

    def _confirmar(self, titulo: str, texto: str) -> bool:
        caixa = QMessageBox(QMessageBox.Icon.Warning, titulo, texto, parent=self)
        sim = caixa.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        caixa.addButton("Não", QMessageBox.ButtonRole.NoRole)
        caixa.exec()
        return caixa.clickedButton() is sim

    # ------------------------------------------------------------------ ações
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
