"""Avaliação de um ponto medido: o erro, somado à incerteza (U), cabe na tolerância do plano?

Mesma regra do programa de calibração da empresa (DQ05), reescrita aqui porque os dois projetos
são separados:

- o ponto só é aprovado se a faixa inteira `[erro − U, erro + U]` ficar dentro da tolerância;
- incerteza ausente **nunca** vale zero: o ponto fica "não avaliado";
- U negativa é usada sem o sinal;
- ponto marcado "U não se aplica" é avaliado só pelo valor, sem U.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Folga para erros de arredondamento do ponto flutuante (ex.: 1,15 − 1,1 = 0,04999…98).
_FOLGA = 1e-9


class Resultado(StrEnum):
    APROVADO = "Aprovado"
    REPROVADO = "Reprovado"
    NAO_INFORMADO = "Não informado"
    NAO_AVALIADO = "Não avaliado"
    PENDENTE = "Pendente"  # só no resultado geral: falta avaliar algum ponto


@dataclass(frozen=True)
class Avaliacao:
    resultado: Resultado
    motivo: str | None = None
    faixa: tuple[float, float] | None = None  # [erro − U, erro + U], para desenhar na tela


def avaliar_ponto(erro: float | None, *, incerteza: float | None,
                  tolerancia_inferior: float | None, tolerancia_superior: float | None,
                  sem_incerteza: bool = False) -> Avaliacao:
    """`erro` = indicação do instrumento − valor de referência (desvio encontrado)."""
    if erro is None:
        return Avaliacao(Resultado.NAO_INFORMADO)
    if incerteza is None and not sem_incerteza:
        return Avaliacao(Resultado.NAO_AVALIADO, "incerteza ausente")
    if tolerancia_inferior is None and tolerancia_superior is None:
        return Avaliacao(Resultado.NAO_AVALIADO, "tolerância ausente")
    u = 0.0 if sem_incerteza else abs(incerteza)
    faixa = (erro - u, erro + u)
    if tolerancia_inferior is not None and faixa[0] < tolerancia_inferior - _FOLGA:
        return Avaliacao(Resultado.REPROVADO, "abaixo do limite inferior", faixa)
    if tolerancia_superior is not None and faixa[1] > tolerancia_superior + _FOLGA:
        return Avaliacao(Resultado.REPROVADO, "acima do limite superior", faixa)
    return Avaliacao(Resultado.APROVADO, None, faixa)


def resultado_geral(resultados: list[Resultado]) -> Resultado:
    """Resultado do certificado inteiro: um ponto reprovado reprova tudo; ponto sem avaliação
    deixa tudo "pendente" (nunca é ignorado)."""
    if not resultados or any(
        r in (Resultado.NAO_INFORMADO, Resultado.NAO_AVALIADO, Resultado.PENDENTE)
        for r in resultados
    ):
        return Resultado.PENDENTE
    if Resultado.REPROVADO in resultados:
        return Resultado.REPROVADO
    return Resultado.APROVADO
