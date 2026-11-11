"""Confere o certificado lido com o plano de calibração do instrumento.

Para cada ponto do certificado: acha o ponto do plano com o mesmo valor nominal, calcula o erro e
avalia `erro ± U` contra a tolerância do plano (a U que vale é a do **certificado**).
Avisos (nunca silenciosos): instrumento sem plano, ponto do plano que não está no certificado,
ponto do certificado que não está no plano, erro que não bate com "encontrado − nominal".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .avaliacao import Avaliacao, Resultado, avaliar_ponto, resultado_geral
from .extracao import CertificadoLido, PontoLido
from .plano import Plano, PlanosDQ05, PontoDoPlano

# Dois valores nominais são "o mesmo ponto" se diferem menos que isto (relativo, com piso).
_TOL_NOMINAL_REL = 1e-6
_TOL_NOMINAL_ABS = 1e-9


@dataclass
class PontoConferido:
    lido: PontoLido
    plano: PontoDoPlano | None
    erro: float | None  # o erro usado na avaliação
    avaliacao: Avaliacao
    avisos: list[str] = field(default_factory=list)


@dataclass
class Conferencia:
    codigo: str | None
    plano_nome: str | None
    resultado: Resultado
    pontos: list[PontoConferido] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _mesmo_nominal(a: float, b: float) -> bool:
    return abs(a - b) <= max(_TOL_NOMINAL_ABS, _TOL_NOMINAL_REL * max(abs(a), abs(b)))


def _casas(x: float) -> int:
    texto = f"{x:.9f}".rstrip("0")
    return len(texto.split(".")[1]) if "." in texto else 0


def _erro_do_ponto(lido: PontoLido) -> tuple[float | None, list[str]]:
    """O erro que o laboratório informou (ou encontrado − nominal, se não informou)."""
    avisos: list[str] = []
    calculado = None if lido.encontrado is None else lido.encontrado - lido.nominal
    if lido.erro is not None:
        if calculado is not None:
            folga = 1.5 * 10 ** -max(_casas(lido.encontrado), _casas(lido.nominal))
            if abs(calculado - lido.erro) > folga:
                avisos.append("o erro do certificado não bate com encontrado − nominal")
        return lido.erro, avisos
    return calculado, avisos


def conferir(certificado: CertificadoLido, planos: PlanosDQ05) -> Conferencia:
    if not certificado.codigo:
        return Conferencia(None, None, Resultado.PENDENTE,
                           avisos=["código do instrumento não encontrado no certificado"])
    plano: Plano | None = planos.plano_do_instrumento(certificado.codigo)
    if plano is None:
        return Conferencia(certificado.codigo, None, Resultado.PENDENTE,
                           avisos=["instrumento sem plano no cadastro (código desconhecido)"])
    conferencia = Conferencia(certificado.codigo, plano.nome, Resultado.PENDENTE)
    resultados: list[Resultado] = []
    achados: set[int] = set()
    for lido in certificado.pontos:
        ponto_plano = next(
            (i for i, p in enumerate(plano.pontos) if _mesmo_nominal(p.nominal, lido.nominal)),
            None,
        )
        erro, avisos = _erro_do_ponto(lido)
        if ponto_plano is None:
            conferencia.pontos.append(PontoConferido(
                lido, None, erro, Avaliacao(Resultado.NAO_AVALIADO, "ponto fora do plano"),
                avisos))
            conferencia.avisos.append(f"ponto {lido.nominal:g} do certificado não está no plano")
            continue
        achados.add(ponto_plano)
        p = plano.pontos[ponto_plano]
        avaliacao = avaliar_ponto(
            erro, incerteza=lido.incerteza, tolerancia_inferior=p.tolerancia_inferior,
            tolerancia_superior=p.tolerancia_superior, sem_incerteza=p.sem_incerteza)
        conferencia.pontos.append(PontoConferido(lido, p, erro, avaliacao, avisos))
        resultados.append(avaliacao.resultado)
    for i, p in enumerate(plano.pontos):
        if i not in achados:
            resultados.append(Resultado.NAO_INFORMADO)
            conferencia.avisos.append(f"ponto {p.nominal:g} do plano não está no certificado")
    conferencia.resultado = resultado_geral(resultados)
    return conferencia
