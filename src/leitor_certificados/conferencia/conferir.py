"""Confere o certificado lido com o plano de calibração do instrumento.

Para cada ponto do certificado: acha o ponto do plano com o mesmo valor nominal, calcula o erro e
avalia `erro ± U` contra a tolerância do plano (a U que vale é a do **certificado**).
Avisos (nunca silenciosos): instrumento sem plano, ponto do plano que não está no certificado,
ponto do certificado que não está no plano, erro que não bate com "encontrado − nominal".

**Conferência de conta** (decisão do usuário, 2026-11-16): o erro pode vir escrito como
"encontrado − nominal" ou "nominal − encontrado" (há laboratório que, no goniômetro, escreve
"Instrumento − Padrão"); quando o certificado traz "Erro Máximo", |erro| + U tem de dar esse
valor. Se os números da linha não fecham a conta nem trocando as colunas, o ponto fica **não
avaliado** (aviso amarelo, parecer PENDENTE): nunca aprova nem reprova com número que não fecha.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .avaliacao import Avaliacao, Resultado, avaliar_ponto, resultado_geral
from .criterio import SituacaoCriterio, aviso_de_criterio, comparar_criterio
from .extracao import CertificadoLido, PontoLido
from .padroes import ConferenciaPadroes, conferir_padroes
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
    avisos: list[str] = field(default_factory=list)  # amarelo: olhar, mas não é problema
    # vermelho: o motivo do problema (pontos fora da tolerância, padrão vencido)
    erros: list[str] = field(default_factory=list)
    faixa_certificado: str | None = None  # só mostrada/avisada: não muda o parecer
    faixa_plano: str | None = None
    cadastro: dict[str, str | None] = field(default_factory=dict)  # do instrumento (comparador)
    # validade dos padrões no dia da calibração (etapa 8): vencido → PENDENTE
    padroes: ConferenciaPadroes | None = None


def _mesmo_nominal(a: float, b: float) -> bool:
    return abs(a - b) <= max(_TOL_NOMINAL_ABS, _TOL_NOMINAL_REL * max(abs(a), abs(b)))


def _casas(x: float) -> int:
    texto = f"{x:.9f}".rstrip("0")
    return len(texto.split(".")[1]) if "." in texto else 0


def _bate(a: float, b: float, *referencias: float) -> bool:
    """a ≈ b, com folga de 1,5 na última casa decimal dos números envolvidos."""
    folga = 1.5 * 10 ** -max(_casas(x) for x in (a, b, *referencias))
    return abs(a - b) <= folga


def _erro_bate(nominal: float, encontrado: float, erro: float) -> bool:
    """O erro fecha a conta com encontrado − nominal, em qualquer um dos dois sinais."""
    diferenca = encontrado - nominal
    return (_bate(diferenca, erro, nominal, encontrado)
            or _bate(-diferenca, erro, nominal, encontrado))


def _erro_maximo_bate(lido: PontoLido, erro: float | None) -> bool:
    """Sem coluna "Erro Máximo" não há o que conferir; com ela, |erro| + U = Erro Máximo."""
    if lido.erro_maximo is None:
        return True
    if erro is None or lido.incerteza is None:
        return False
    return _bate(abs(erro) + lido.incerteza, lido.erro_maximo, erro, lido.incerteza)


def _erro_do_ponto(lido: PontoLido) -> tuple[float | None, list[str]]:
    """O erro que o laboratório informou (ou encontrado − nominal, se não informou)."""
    avisos: list[str] = []
    calculado = None if lido.encontrado is None else lido.encontrado - lido.nominal
    erro = lido.erro if lido.erro is not None else calculado
    if lido.erro is not None and calculado is not None and not _erro_bate(
            lido.nominal, lido.encontrado, lido.erro):
        avisos.append("o erro do certificado não bate com encontrado − nominal")
    if not _erro_maximo_bate(lido, erro):
        avisos.append("|erro| + U não dá o Erro Máximo do certificado")
    return erro, avisos


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
        if not any(p.aceita(candidato, lido.escala) for p in plano.pontos):
            continue
        resto = [(j, x) for j, x in enumerate(lido.numeros) if j != i]
        for (ja, e), (jb, r) in ((a, b) for a in resto for b in resto if a[0] != b[0]):
            if not _erro_bate(candidato, e, r):
                continue
            sobra = [x for j, x in resto if j not in (ja, jb)]
            u = lido.incerteza if lido.incerteza in sobra else min(
                (x for x in sobra if x > 0), default=None)
            novo = dataclasses.replace(lido, nominal=candidato, encontrado=e, erro=r,
                                       incerteza=u)
            if _erro_maximo_bate(novo, r):  # com "Erro Máximo", a conta tem de fechar
                achadas.append(novo)
    unicas = {(a.nominal, a.encontrado, a.erro) for a in achadas}
    return achadas[0] if len(unicas) == 1 else None


def _ponto_do_plano(plano: Plano, nominal: float, usados: set[int],
                    escala: str | None = None) -> int | None:
    """O ponto do plano com este nominal (ou, no durômetro, o intervalo da mesma escala que
    contém o padrão). O plano pode repetir o nominal (ex.: goniômetro com 0° e 90° em cada
    quadrante): os repetidos são casados **na ordem**, o 1º do certificado com o 1º do plano,
    o 2º com o 2º… Só se todos já foram usados, volta ao primeiro."""
    iguais = [i for i, p in enumerate(plano.pontos) if p.aceita(nominal, escala)]
    livres = [i for i in iguais if i not in usados]
    return (livres or iguais or [None])[0]


def conferir(certificado: CertificadoLido, planos: PlanosDQ05,
             padroes_calibrados: bool = False) -> Conferencia:
    """Confere os pontos com o plano e a validade dos padrões (decisões do usuário, 2026-11-16):
    padrão vencido no dia da calibração deixa PENDENTE um parecer que seria APROVADO; se os
    pontos reprovam, continua REPROVADO. Sempre dizendo o motivo (em `erros`). Validade não lida
    também deixa PENDENTE (aviso amarelo dizendo o que conferir), a não ser que a pessoa
    marque `padroes_calibrados` (os padrões vêm em outro certificado; pedido do usuário,
    2026-11-17). Padrão VENCIDO continua valendo: a marca não esconde isso."""
    conferencia = _conferir_pontos(certificado, planos)
    fora = [p.lido.nominal for p in conferencia.pontos
            if p.avaliacao.resultado == Resultado.REPROVADO]
    if fora:
        conferencia.erros.append(
            f"{len(fora)} ponto(s) fora da tolerância: " + "; ".join(f"{n:g}" for n in fora))
    padroes = conferir_padroes(
        [(p.codigo, p.validade, p.caixa) for p in certificado.padroes],
        certificado.data_calibracao)
    conferencia.padroes = padroes
    conferencia.avisos += padroes.avisos
    if padroes.algum_vencido:
        if conferencia.resultado == Resultado.APROVADO:
            conferencia.resultado = Resultado.PENDENTE
            sufixo = " — parecer pendente (os pontos passam, mas o padrão estava vencido)"
        elif conferencia.resultado == Resultado.REPROVADO:
            sufixo = " — o parecer continua reprovado pelos pontos"
        else:
            sufixo = ""
        conferencia.erros += [e + sufixo for e in padroes.erros]
    elif padroes.falta_conferir and padroes_calibrados:
        conferencia.avisos = [a for a in conferencia.avisos if a not in padroes.avisos]
    elif padroes.falta_conferir and conferencia.resultado == Resultado.APROVADO:
        conferencia.resultado = Resultado.PENDENTE
        conferencia.avisos.append("parecer pendente: os pontos passam, mas a validade dos "
                                  "padrões não foi conferida — confira no certificado")
    return conferencia


def _desempatar_pelos_pontos(certificado: CertificadoLido, planos: PlanosDQ05,
                             candidatos: list[str]) -> str | None:
    """Dúvida entre instrumentos (ex.: "PAQ-7" pode ser PAQ-007 ou PAQ-0007): fica com o único
    cujo plano tem todos os pontos nominais do certificado (ideia do usuário, 2026-11-16).
    Se mais de um (ou nenhum) servir, não escolhe."""
    nominais = {p.nominal for p in certificado.pontos}
    if not nominais:
        return None
    servem = []
    for chave in candidatos:
        plano = planos.plano_do_instrumento(chave)
        if plano and all(any(q.aceita(n) for q in plano.pontos) for n in nominais):
            servem.append(chave)
    return servem[0] if len(servem) == 1 else None


def _conferir_pontos(certificado: CertificadoLido, planos: PlanosDQ05) -> Conferencia:
    codigo = achar_codigo(certificado, planos)
    if not codigo:
        return Conferencia(None, None, Resultado.PENDENTE,
                           avisos=["código do instrumento não encontrado no certificado"])
    if not planos.conhece(codigo) and len(candidatos := planos.candidatos(codigo)) > 1:
        codigo = _desempatar_pelos_pontos(certificado, planos, candidatos) or codigo
    certificado = dataclasses.replace(certificado, codigo=codigo)
    plano: Plano | None = planos.plano_do_instrumento(certificado.codigo)
    if plano is None:
        return Conferencia(certificado.codigo, None, Resultado.PENDENTE,
                           avisos=["instrumento sem plano no cadastro (código desconhecido)"])
    conferencia = Conferencia(certificado.codigo, plano.nome, Resultado.PENDENTE,
                              faixa_certificado=certificado.faixa, faixa_plano=plano.faixa,
                              cadastro=plano.cadastro)
    # a faixa (e o resto do cadastro) é comparada no comparador do painel Instrumento
    # (conferencia/cadastro.py): só avisa ali, nunca muda o parecer
    resultados: list[Resultado] = []
    achados: set[int] = set()
    for lido in certificado.pontos:
        ponto_plano = _ponto_do_plano(plano, lido.nominal, achados, lido.escala)
        if ponto_plano is None:
            # o modelo marcou mais de um número como nominal: vale o que existe no plano
            for outro in lido.nominais:
                if (i := _ponto_do_plano(plano, outro, achados, lido.escala)) is not None:
                    lido, ponto_plano = dataclasses.replace(lido, nominal=outro), i
                    break
        erro, avisos = _erro_do_ponto(lido)
        if ponto_plano is None or avisos or (lido.encontrado is None and lido.erro is None):
            novo = reatribuir(lido, plano)
            if novo is not None:
                lido = novo
                ponto_plano = _ponto_do_plano(plano, lido.nominal, achados, lido.escala)
                erro, avisos = _erro_do_ponto(lido)
                avisos = [*avisos, "colunas reatribuídas com ajuda do plano"]
        if avisos and ponto_plano is not None:
            # os números não fecham a conta nem trocando as colunas: não avalia com eles
            conferencia.pontos.append(PontoConferido(
                lido, plano.pontos[ponto_plano], erro,
                Avaliacao(Resultado.NAO_AVALIADO, "os números da linha não fecham a conta"),
                avisos))
            achados.add(ponto_plano)
            resultados.append(Resultado.NAO_AVALIADO)
            conferencia.avisos.append(
                f"ponto {lido.nominal:g}: os números não fecham a conta ({avisos[0]}) — "
                "confira no certificado")
            continue
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
            nome = (f"{p.nominal:g}" if p.nominal is not None
                    else f"{p.minimo:g} a {p.maximo:g} {p.escala}")
            conferencia.avisos.append(f"ponto {nome} do plano não está no certificado")
    conferencia.resultado = resultado_geral(resultados)
    return conferencia
