"""Confere se cada padrão usado estava **dentro da validade no dia da calibração** (etapa 8,
ADR 0010).

Regras (decisões do usuário, 2026-11-13 e 2026-11-16):
- validade só com mês e ano ("07/2026") vale **o mês inteiro** (até 31/07/2026);
- padrão **vencido** no dia da calibração → o parecer vira **PENDENTE** (alguém precisa olhar
  antes de aceitar o certificado), com um aviso dizendo qual padrão venceu;
- validade **não lida** (ou data da calibração não lida, ou nenhum padrão achado) → só **aviso
  amarelo**: o parecer não muda.

As datas vêm escritas de muitos jeitos: "12/08/2026", "12.08.2026", "2026-08-12",
"12 de agosto de 2026", "12/ago/2026", "17-11-25" (ano com 2 dígitos) e, na validade, "08/2027".
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
_MESES_EN = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

_DIA_MES_ANO = re.compile(r"(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4}|\d{2})(?!\d)")
_ANO_MES_DIA = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_EXTENSO = re.compile(r"(?<!\d)(\d{1,2})\s*(?:de\s+)?([a-z]{3})[a-z]*\.?\s*(?:de\s+)?/?\s*(\d{4})")
_EXTENSO_BARRA = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*([a-z]{3})[a-z]*\s*/\s*(\d{4})")
_MES_ANO = re.compile(r"(?<![\d/.\-])(\d{1,2})\s*[/.\-]\s*(\d{4})(?![\d/.\-])")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _ano(texto: str) -> int:
    ano = int(texto)
    return ano + 2000 if ano < 100 else ano


def _data(dia: int, mes: int, ano: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _mes_por_nome(nome: str) -> int | None:
    for meses in (_MESES, _MESES_EN):
        if nome[:3] in meses:
            return meses.index(nome[:3]) + 1
    return None


def ler_data(texto: str | None) -> date | None:
    """A primeira data completa (dia, mês e ano) escrita no texto, ou None."""
    if not texto:
        return None
    t = _sem_acento(texto)
    if achado := _ANO_MES_DIA.search(t):
        return _data(int(achado[3]), int(achado[2]), int(achado[1]))
    if achado := _DIA_MES_ANO.search(t):
        return _data(int(achado[1]), int(achado[2]), _ano(achado[3]))
    for regra in (_EXTENSO_BARRA, _EXTENSO):
        if (achado := regra.search(t)) and (mes := _mes_por_nome(achado[2])):
            return _data(int(achado[1]), mes, int(achado[3]))
    return None


@dataclass(frozen=True)
class Validade:
    ate: date  # último dia em que o padrão vale
    so_mes: bool  # escrita só com mês e ano (vale o mês inteiro)


def ler_validade(texto: str | None) -> Validade | None:
    """A validade do padrão: data completa, ou mês/ano ("07/2026" → até 31/07/2026)."""
    if not texto:
        return None
    if (completa := ler_data(texto)) is not None:
        return Validade(completa, False)
    if achado := _MES_ANO.search(_sem_acento(texto)):
        mes, ano = int(achado[1]), int(achado[2])
        if 1 <= mes <= 12:
            return Validade(date(ano, mes, calendar.monthrange(ano, mes)[1]), True)
    return None


class SituacaoPadrao(Enum):
    EM_DIA = "em dia"
    VENCIDO = "vencido"
    NAO_CONFERIDO = "não conferido"  # validade ou data da calibração não lida


@dataclass(frozen=True)
class PadraoConferido:
    codigo: str | None
    validade_texto: str | None  # como está escrita no certificado
    validade: Validade | None
    situacao: SituacaoPadrao
    motivo: str = ""  # por que não foi conferido
    caixa: tuple[float, float, float, float] | None = None  # a linha na folha


@dataclass
class ConferenciaPadroes:
    data_calibracao_texto: str | None
    data_calibracao: date | None
    padroes: list[PadraoConferido] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def algum_vencido(self) -> bool:
        return any(p.situacao == SituacaoPadrao.VENCIDO for p in self.padroes)


def data_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def conferir_padroes(padroes: list[tuple[str | None, str | None, tuple | None]],
                     data_calibracao_texto: str | None) -> ConferenciaPadroes:
    """`padroes` = [(código, validade escrita, caixa da linha), …] como o modelo leu."""
    data_cal = ler_data(data_calibracao_texto)
    resultado = ConferenciaPadroes(data_calibracao_texto, data_cal)
    if not padroes:
        resultado.avisos.append("padrões não encontrados no certificado: validade dos padrões "
                                "não conferida")
        return resultado
    if data_cal is None:
        resultado.avisos.append(
            ("data da calibração não encontrada" if not data_calibracao_texto
             else f"data da calibração não entendida ({data_calibracao_texto})")
            + ": validade dos padrões não conferida")
    for codigo, validade_texto, caixa in padroes:
        validade = ler_validade(validade_texto)
        nome = codigo or "sem código"
        if validade is None:
            motivo = ("validade não encontrada" if not validade_texto
                      else f"validade não entendida ({validade_texto})")
            resultado.padroes.append(PadraoConferido(
                codigo, validade_texto, None, SituacaoPadrao.NAO_CONFERIDO, motivo, caixa))
            resultado.avisos.append(f"padrão {nome}: {motivo}")
        elif data_cal is None:
            resultado.padroes.append(PadraoConferido(
                codigo, validade_texto, validade, SituacaoPadrao.NAO_CONFERIDO,
                "sem a data da calibração", caixa))
        elif validade.ate < data_cal:
            resultado.padroes.append(PadraoConferido(
                codigo, validade_texto, validade, SituacaoPadrao.VENCIDO, "", caixa))
            resultado.avisos.append(
                f"padrão {nome} vencido: validade até {data_br(validade.ate)}, calibração em "
                f"{data_br(data_cal)} — parecer pendente")
        else:
            resultado.padroes.append(PadraoConferido(
                codigo, validade_texto, validade, SituacaoPadrao.EM_DIA, "", caixa))
    return resultado
