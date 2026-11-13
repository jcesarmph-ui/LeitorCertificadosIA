"""Confere o certificado lido com o plano de calibração do instrumento.

Para cada ponto do certificado: acha o ponto do plano com o mesmo valor nominal, calcula o erro e
avalia `erro ± U` contra a tolerância do plano (a U que vale é a do **certificado**).
Avisos (nunca silenciosos): instrumento sem plano, ponto do plano que não está no certificado,
ponto do certificado que não está no plano, erro que não bate com "encontrado − nominal".
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .avaliacao import Avaliacao, Resultado, avaliar_ponto, resultado_geral
from .criterio import SituacaoCriterio, aviso_de_criterio, comparar_criterio
from .extracao import CertificadoLido, PontoLido
from .faixa import comparar_faixas
from .plano import Plano, PlanosDQ05, PontoDoPlano, normalizar_codigo

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
    # critério de aceitação do certificado × tolerância do plano (só avisa; ADR 0009)
    criterio: SituacaoCriterio = SituacaoCriterio.NAO_COMPARADO


@dataclass
class Conferencia:
    codigo: str | None
    plano_nome: str | None
    resultado: Resultado
    pontos: list[PontoConferido] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    faixa_certificado: str | None = None  # só mostrada/avisada: não muda o parecer
    faixa_plano: str | None = None


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


def achar_codigo(certificado: CertificadoLido, planos: PlanosDQ05) -> str | None:
    """O código do instrumento: o que o modelo achou, ou — se o cadastro não o conhece — qualquer
    palavra (ou 2-3 palavras seguidas, como "PAQ - 016") da folha que seja um código do cadastro."""
    if certificado.codigo and planos.conhece(certificado.codigo):
        return certificado.codigo
    textos = certificado.textos
    for tamanho in (1, 2, 3):
        for i in range(len(textos) - tamanho + 1):
            candidato = " ".join(textos[i:i + tamanho])
            if len(normalizar_codigo(candidato)) >= 4 and planos.conhece(candidato):
                return candidato
    return certificado.codigo


def reatribuir(lido: PontoLido, plano: Plano) -> PontoLido | None:
    """Quando o modelo trocou as colunas: usa o plano para refazer o ponto.

    O nominal tem de ser um número da linha que exista no plano, e o erro tem de ser
    "encontrado − nominal" (os números da linha formam esse trio). Devolve None se não houver
    uma única atribuição possível."""
    achadas: list[PontoLido] = []
    for i, candidato in enumerate(lido.numeros):
        if not any(_mesmo_nominal(p.nominal, candidato) for p in plano.pontos):
            continue
        resto = [(j, x) for j, x in enumerate(lido.numeros) if j != i]
        for (ja, e), (jb, r) in ((a, b) for a in resto for b in resto if a[0] != b[0]):
            folga = 1.6 * 10 ** -max(_casas(e), _casas(candidato), _casas(r))
            if abs((e - candidato) - r) > folga:
                continue
            sobra = [x for j, x in resto if j not in (ja, jb)]
            u = lido.incerteza if lido.incerteza in sobra else min(
                (x for x in sobra if x > 0), default=None)
            achadas.append(PontoLido(candidato, e, r, u, lido.caixa, lido.numeros,
                                     lido.erro_maximo, lido.criterio))
    unicas = {(a.nominal, a.encontrado, a.erro) for a in achadas}
    return achadas[0] if len(unicas) == 1 else None


def _ponto_do_plano(plano: Plano, nominal: float, usados: set[int]) -> int | None:
    """O ponto do plano com este nominal. O plano pode repetir o nominal (ex.: goniômetro com
    0° e 90° em cada quadrante): os repetidos são casados **na ordem**, o 1º do certificado com
    o 1º do plano, o 2º com o 2º… Só se todos já foram usados, volta ao primeiro."""
    iguais = [i for i, p in enumerate(plano.pontos) if _mesmo_nominal(p.nominal, nominal)]
    livres = [i for i in iguais if i not in usados]
    return (livres or iguais or [None])[0]


def conferir(certificado: CertificadoLido, planos: PlanosDQ05) -> Conferencia:
    codigo = achar_codigo(certificado, planos)
    if not codigo:
        return Conferencia(None, None, Resultado.PENDENTE,
                           avisos=["código do instrumento não encontrado no certificado"])
    certificado = CertificadoLido(codigo, certificado.pontos, certificado.textos,
                                  certificado.faixa)
    plano: Plano | None = planos.plano_do_instrumento(certificado.codigo)
    if plano is None:
        return Conferencia(certificado.codigo, None, Resultado.PENDENTE,
                           avisos=["instrumento sem plano no cadastro (código desconhecido)"])
    conferencia = Conferencia(certificado.codigo, plano.nome, Resultado.PENDENTE,
                              faixa_certificado=certificado.faixa, faixa_plano=plano.faixa)
    aviso_faixa = comparar_faixas(certificado.faixa, plano.faixa).aviso
    if aviso_faixa:  # decisão do usuário: faixa diferente só avisa; o parecer vem da tolerância
        conferencia.avisos.append(aviso_faixa)
    resultados: list[Resultado] = []
    achados: set[int] = set()
    for lido in certificado.pontos:
        ponto_plano = _ponto_do_plano(plano, lido.nominal, achados)
        if ponto_plano is None:
            # o modelo marcou mais de um número como nominal: vale o que existe no plano
            for outro in lido.nominais:
                if (i := _ponto_do_plano(plano, outro, achados)) is not None:
                    lido, ponto_plano = dataclasses.replace(lido, nominal=outro), i
                    break
        erro, avisos = _erro_do_ponto(lido)
        if ponto_plano is None or avisos or (lido.encontrado is None and lido.erro is None):
            novo = reatribuir(lido, plano)
            if novo is not None:
                lido = novo
                ponto_plano = _ponto_do_plano(plano, lido.nominal, achados)
                erro, avisos = _erro_do_ponto(lido)
                avisos = [*avisos, "colunas reatribuídas com ajuda do plano"]
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
        criterio = comparar_criterio(lido.criterio, p.tolerancia_inferior, p.tolerancia_superior)
        conferencia.pontos.append(PontoConferido(lido, p, erro, avaliacao, avisos, criterio))
        resultados.append(avaliacao.resultado)
    # decisão do usuário: critério diferente do plano só avisa (como a faixa)
    comparados = [c for c in conferencia.pontos if c.criterio != SituacaoCriterio.NAO_COMPARADO]
    conferencia.avisos += aviso_de_criterio(
        [(c.lido.nominal, c.lido.criterio, c.plano.tolerancia_inferior,
          c.plano.tolerancia_superior)
         for c in comparados if c.criterio == SituacaoCriterio.DIFERENTE],
        len(comparados))
    for i, p in enumerate(plano.pontos):
        if i not in achados:
            resultados.append(Resultado.NAO_INFORMADO)
            conferencia.avisos.append(f"ponto {p.nominal:g} do plano não está no certificado")
    conferencia.resultado = resultado_geral(resultados)
    return conferencia
