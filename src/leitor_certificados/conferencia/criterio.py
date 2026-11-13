"""Compara o critério de aceitação do certificado com a tolerância do plano (decisão do usuário,
2026-11-13, ADR 0009): só **avisa** em amarelo (não muda o parecer), igual à faixa.

Alguns laboratórios (ex.: o estilo da Laftec) trazem a coluna "Critério de aceitação ±" — o
limite que **o cliente** informou ao laboratório. Se ele não for o mesmo do nosso plano, o
laboratório julgou o instrumento com outra régua: vale a pena olhar. O parecer continua vindo
da nossa regra (erro ± U contra a tolerância do plano).

O critério é simétrico (± c), então ele é igual ao plano só quando o plano vai de −c a +c.
"""

from __future__ import annotations

from enum import Enum

# Folga para arredondamento (o critério vem escrito com poucas casas; o plano é um REAL do banco).
_FOLGA_REL = 1e-6
_FOLGA_ABS = 1e-9


class SituacaoCriterio(Enum):
    IGUAL = "igual"
    DIFERENTE = "diferente"
    NAO_COMPARADO = "não comparado"  # certificado sem critério ou plano sem tolerância


def _igual(a: float, b: float) -> bool:
    return abs(a - b) <= max(_FOLGA_ABS, _FOLGA_REL * max(abs(a), abs(b)))


def comparar_criterio(criterio: float | None, tolerancia_inferior: float | None,
                      tolerancia_superior: float | None) -> SituacaoCriterio:
    if criterio is None or (tolerancia_inferior is None and tolerancia_superior is None):
        return SituacaoCriterio.NAO_COMPARADO
    c = abs(criterio)
    if (tolerancia_inferior is not None and _igual(tolerancia_inferior, -c)
            and tolerancia_superior is not None and _igual(tolerancia_superior, c)):
        return SituacaoCriterio.IGUAL
    return SituacaoCriterio.DIFERENTE


def numero_br(x: float) -> str:
    """0.05 → "0,05" (sem zeros sobrando)."""
    return f"{x:g}".replace(".", ",")


def descrever_criterio(criterio: float) -> str:
    return f"± {numero_br(abs(criterio))}"


def descrever_tolerancia_curta(inferior: float | None, superior: float | None) -> str:
    """"± 0,03" quando é simétrica; senão "−0,02 a +0,03" (ou só um dos lados)."""
    if inferior is not None and superior is not None and _igual(-inferior, superior):
        return f"± {numero_br(superior)}"
    partes = []
    if inferior is not None:
        partes.append(f"mín. {numero_br(inferior)}")
    if superior is not None:
        partes.append(f"máx. {numero_br(superior)}")
    return " / ".join(partes)


def aviso_de_criterio(diferentes: list[tuple[float, float, float | None, float | None]],
                      total_comparados: int) -> list[str]:
    """Junta os pontos com critério diferente num aviso só por par (critério, tolerância).

    `diferentes` = [(nominal, critério, tolerância inferior, tolerância superior), …]."""
    grupos: dict[tuple[str, str], list[float]] = {}
    for nominal, criterio, inferior, superior in diferentes:
        chave = (descrever_criterio(criterio), descrever_tolerancia_curta(inferior, superior))
        grupos.setdefault(chave, []).append(nominal)
    avisos = []
    for (crit, tol), nominais in grupos.items():
        onde = ("" if len(nominais) == total_comparados
                else " nos pontos " + ", ".join(numero_br(n) for n in nominais))
        avisos.append(f"critério de aceitação do certificado ({crit}) diferente da tolerância "
                      f"do plano ({tol}){onde}")
    return avisos
