"""Comparador "cadastro × certificado" do painel Instrumento (pedido do usuário, 2026-11-13).

Compara o que o cadastro do instrumento diz (tipo, fabricante, faixa, resolução) com o que o
modelo leu no certificado. **Só informa**: o que bate ganha um check verde; o que não bate,
um aviso amarelo. **Nunca muda o parecer** — às vezes uma letra lida diferente basta para não
bater, e isso não pode reprovar um certificado.

Se um dos lados não tem o dado (vazio ou "-"), a linha só mostra o que há, sem marca.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from .faixa import Situacao, comparar_faixas
from .plano import normalizar_codigo


class Bate(Enum):
    SIM = "bate"
    NAO = "não bate"
    SEM_DADO = "sem dado"  # falta de um dos lados: não há o que comparar


@dataclass(frozen=True)
class ItemComparado:
    chave: str  # "codigo", "tipo", "fabricante", "faixa", "resolucao"
    nome: str  # como aparece na tela
    cadastro: str | None
    certificado: str | None
    bate: Bate


# (chave, nome na tela) na ordem do painel
CAMPOS = (("codigo", "Código"), ("tipo", "Tipo"), ("fabricante", "Fabricante"),
          ("faixa", "Faixa"), ("resolucao", "Resolução"))

_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _vazio(texto: str | None) -> bool:
    return texto is None or texto.strip() in ("", "-", "—", "N/A", "n/a")


def _palavras(texto: str) -> list[str]:
    """Minúsculas, sem acento e sem pontuação: "Paquímetro Digital" → ["paquimetro", "digital"]."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", sem_acento)


def _texto_bate(cadastro: str, certificado: str) -> bool:
    """Iguais sem ligar para maiúsculas/acentos, ou um contém o outro em palavras inteiras
    ("Paquímetro" × "Paquímetro Digital")."""
    a, b = _palavras(cadastro), _palavras(certificado)
    if not a or not b:
        return False
    curto, longo = (a, b) if len(a) <= len(b) else (b, a)
    return any(longo[i:i + len(curto)] == curto for i in range(len(longo) - len(curto) + 1))


def _numero_bate(cadastro: str, certificado: str) -> bool:
    """Resolução: só o primeiro número de cada lado ("0,01" × "0.01 mm")."""
    a, b = _NUMERO.search(cadastro), _NUMERO.search(certificado)
    if not a or not b:
        return False
    return abs(float(a.group().replace(",", ".")) - float(b.group().replace(",", "."))) < 1e-9


def comparar_campo(chave: str, cadastro: str | None, certificado: str | None) -> Bate:
    if _vazio(cadastro) or _vazio(certificado):
        return Bate.SEM_DADO
    if chave == "codigo":
        iguais = normalizar_codigo(cadastro) == normalizar_codigo(certificado)
    elif chave == "faixa":
        iguais = comparar_faixas(certificado, cadastro).situacao == Situacao.IGUAL
    elif chave == "resolucao":
        iguais = _numero_bate(cadastro, certificado)
    else:
        iguais = _texto_bate(cadastro, certificado)
    return Bate.SIM if iguais else Bate.NAO


def comparar_com_cadastro(cadastro: dict[str, str | None],
                          certificado: dict[str, str | None]) -> list[ItemComparado]:
    """Uma linha por campo de `CAMPOS`, com o valor de cada lado e se bate."""
    return [
        ItemComparado(chave, nome, cadastro.get(chave), certificado.get(chave),
                      comparar_campo(chave, cadastro.get(chave), certificado.get(chave)))
        for chave, nome in CAMPOS
    ]
