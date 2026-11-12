"""Compara a faixa do certificado com a faixa do instrumento no plano (decisão do usuário,
2026-11-12): só **avisa** (não muda o parecer), olhando **mínimo e máximo**.

A faixa é texto livre nos dois lados ("0 mm | 500 mm" no certificado; "0-500", "0 a 25 mm",
"0 - 360°", "5000 / 3000", "7,5 bar" no plano). Só é um intervalo quando há dois números ligados
por "a", "-", "–" ou "|"; o resto ("5000 / 3000", um número só) não é comparado, só mostrado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_NUMERO = r"\d+(?:[.,]\d+)?"
_INTERVALO = re.compile(
    rf"(?<![\w.,])({_NUMERO})\s*[a-zA-Zµ°%]*\s*(?:a|à|até|-|–|\|)\s*({_NUMERO})", re.IGNORECASE)


class Situacao(Enum):
    IGUAL = "igual"
    DIFERENTE = "diferente"
    NAO_COMPARADA = "não comparada"


@dataclass(frozen=True)
class ComparacaoFaixa:
    situacao: Situacao
    aviso: str | None  # texto do aviso amarelo (None quando está tudo certo)


def _para_float(texto: str) -> float:
    return float(texto.replace(",", "."))


def ler_intervalo(texto: str | None) -> tuple[float, float] | None:
    """(mínimo, máximo) se o texto é um intervalo; senão None."""
    if not texto:
        return None
    achado = _INTERVALO.search(texto)
    if not achado:
        return None
    minimo, maximo = _para_float(achado.group(1)), _para_float(achado.group(2))
    return (minimo, maximo) if minimo <= maximo else None


def comparar_faixas(certificado: str | None, plano: str | None) -> ComparacaoFaixa:
    """Compara só quando o plano tem faixa; sem faixa no plano não há o que conferir."""
    if not plano or not plano.strip():
        return ComparacaoFaixa(Situacao.NAO_COMPARADA, None)
    if not certificado or not certificado.strip():
        return ComparacaoFaixa(Situacao.NAO_COMPARADA,
                               f"faixa não encontrada no certificado (plano: {plano.strip()})")
    do_cert, do_plano = ler_intervalo(certificado), ler_intervalo(plano)
    if do_cert is None or do_plano is None:
        return ComparacaoFaixa(
            Situacao.NAO_COMPARADA,
            f"faixa não comparada (certificado: {certificado.strip()}; plano: {plano.strip()})")
    if all(abs(a - b) < 1e-9 for a, b in zip(do_cert, do_plano, strict=True)):
        return ComparacaoFaixa(Situacao.IGUAL, None)
    return ComparacaoFaixa(
        Situacao.DIFERENTE,
        f"faixa do certificado ({certificado.strip()}) diferente da do plano ({plano.strip()})")
