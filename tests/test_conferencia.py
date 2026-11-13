"""Testes da etapa 4: regra erro ± U, leitura do plano (só leitura) e conferência de ponta a ponta.

O teste de ponta a ponta usa certificados e planos 100 % inventados: lê o PDF, o modelo acha os
campos, o plano é consultado e o parecer tem de bater com a resposta calculada do gabarito.
"""

import json
import sqlite3

import pytest

from leitor_certificados.aprendizado.modelo import treinar
from leitor_certificados.conferencia.avaliacao import Resultado, avaliar_ponto, resultado_geral
from leitor_certificados.conferencia.conferir import conferir
from leitor_certificados.conferencia.extracao import montar_certificado, para_numero
from leitor_certificados.conferencia.plano import PlanosDQ05, normalizar_codigo
from leitor_certificados.ficticio.gerar import gerar_um
from leitor_certificados.ficticio.plano import criar_banco_de_planos
from leitor_certificados.leitura.ler import ler_pdf


def test_ponto_so_passa_se_a_faixa_inteira_cabe_na_tolerancia():
    base = {"tolerancia_inferior": -0.05, "tolerancia_superior": 0.05}
    assert avaliar_ponto(0.03, incerteza=0.02, **base).resultado == Resultado.APROVADO
    # 0,04 + 0,02 = 0,06 passa de 0,05: só o erro cabe, o erro com a incerteza não
    assert avaliar_ponto(0.04, incerteza=0.02, **base).resultado == Resultado.REPROVADO
    assert avaliar_ponto(-0.04, incerteza=0.02, **base).resultado == Resultado.REPROVADO
    # no limite exato (com folga de arredondamento) ainda aprova
    assert avaliar_ponto(0.04, incerteza=0.01, **base).resultado == Resultado.APROVADO


def test_incerteza_ausente_nunca_vale_zero():
    base = {"tolerancia_inferior": -0.05, "tolerancia_superior": 0.05}
    assert avaliar_ponto(0.0, incerteza=None, **base).resultado == Resultado.NAO_AVALIADO
    assert avaliar_ponto(0.0, incerteza=None, sem_incerteza=True,
                         **base).resultado == Resultado.APROVADO
    assert avaliar_ponto(0.0, incerteza=-0.01, **base).resultado == Resultado.APROVADO  # sem sinal
    assert avaliar_ponto(None, incerteza=0.01, **base).resultado == Resultado.NAO_INFORMADO


def test_resultado_geral():
    A, R, N = Resultado.APROVADO, Resultado.REPROVADO, Resultado.NAO_INFORMADO
    assert resultado_geral([A, A]) == A
    assert resultado_geral([A, R]) == R
    assert resultado_geral([A, N]) == Resultado.PENDENTE  # ponto faltando nunca é ignorado
    assert resultado_geral([]) == Resultado.PENDENTE


def test_para_numero():
    assert para_numero("-0,001") == -0.001
    assert para_numero("+0.5") == 0.5
    assert para_numero("1.350,00") == 1350.0
    assert para_numero("1,350.00") == 1350.0
    assert para_numero("−2,5") == -2.5
    assert para_numero("abc") is None and para_numero("") is None


def test_codigo_igual_com_qualquer_escrita():
    assert normalizar_codigo("paq - 018") == normalizar_codigo("PAQ-018") == "PAQ018"


@pytest.fixture(scope="module")
def mundo(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("conferencia")
    gabaritos = [json.loads(gerar_um(pasta, n).read_text(encoding="utf-8")) for n in range(1, 41)]
    paginas = [ler_pdf(pasta / g["digital"]["arquivo"])[0] for g in gabaritos]
    modelo = treinar(paginas[:30], [g["digital"]["campos"] for g in gabaritos[:30]])
    banco = pasta / "planos.db"
    certo = criar_banco_de_planos(banco, [g["certificado"] for g in gabaritos])
    return modelo, paginas, gabaritos, banco, certo


def test_plano_e_aberto_so_para_leitura(mundo):
    _, _, gabaritos, banco, _ = mundo
    planos = PlanosDQ05(banco)
    try:
        assert planos.conhece(gabaritos[0]["certificado"]["codigo"].lower())
        assert planos.plano_do_instrumento("XX-0000") is None
        with pytest.raises(sqlite3.OperationalError):  # gravar é impossível, mesmo de propósito
            planos._con.execute("DELETE FROM planos")
    finally:
        planos.fechar()


def test_conferencia_de_ponta_a_ponta_em_certificados_novos(mundo):
    modelo, paginas, gabaritos, banco, certo = mundo
    planos = PlanosDQ05(banco)
    try:
        acertos = 0
        for pagina, gab in zip(paginas[30:], gabaritos[30:], strict=True):
            lido = montar_certificado(modelo, pagina)
            resultado = conferir(lido, planos)
            acertos += resultado.resultado == certo[gab["certificado"]["id"]]
        assert acertos >= 8, f"{acertos} de 10 pareceres certos"
    finally:
        planos.fechar()


def test_instrumento_desconhecido_fica_pendente_com_aviso(mundo):
    modelo, paginas, _, banco, _ = mundo
    planos = PlanosDQ05(banco)
    try:
        lido = montar_certificado(modelo, paginas[0])
        lido = type(lido)("ZZ-9999", lido.pontos)
        resultado = conferir(lido, planos)
        assert resultado.resultado == Resultado.PENDENTE and resultado.avisos
    finally:
        planos.fechar()


# --- faixa: só avisa (decisão do usuário, 2026-11-12), olhando mínimo e máximo -----------------

def test_faixa_le_os_formatos_do_certificado_e_do_cadastro():
    from leitor_certificados.conferencia.faixa import ler_intervalo

    assert ler_intervalo("0 mm | 500 mm") == (0, 500)
    assert ler_intervalo("0-500") == (0, 500)
    assert ler_intervalo("0 a 25 mm") == (0, 25)
    assert ler_intervalo("0 - 360°") == (0, 360)
    assert ler_intervalo("0,02 a 1,00") == (0.02, 1.0)
    assert ler_intervalo("0-25 /") == (0, 25)
    assert ler_intervalo("25 to 50 mm") == (25, 50)  # certificado em inglês
    assert ler_intervalo("0 a 25  mm / esp 2,0 mm máx.") == (0, 25)
    assert ler_intervalo("5000 / 3000") is None  # não é intervalo: só mostrada
    assert ler_intervalo("7,5 bar") is None
    assert ler_intervalo(None) is None


def test_faixa_igual_nao_avisa_e_diferente_avisa_sem_mudar_o_parecer():
    from leitor_certificados.conferencia.faixa import Situacao, comparar_faixas

    assert comparar_faixas("0 mm | 500 mm", "0-500").situacao == Situacao.IGUAL
    assert comparar_faixas("0 mm | 500 mm", "0-500").aviso is None
    diferente = comparar_faixas("0 mm | 300 mm", "0-500")
    assert diferente.situacao == Situacao.DIFERENTE and "diferente" in diferente.aviso
    assert comparar_faixas("0 mm | 500 mm", None).aviso is None  # plano sem faixa: nada a conferir
    assert "não encontrada" in comparar_faixas(None, "0-500").aviso
    assert "não comparada" in comparar_faixas("0 a 25", "5000 / 3000").aviso


# --- critério de aceitação do certificado: só avisa (decisão do usuário, 2026-11-13) ------------

def test_criterio_igual_so_quando_o_plano_vai_de_menos_c_a_mais_c():
    from leitor_certificados.conferencia.criterio import SituacaoCriterio as S
    from leitor_certificados.conferencia.criterio import comparar_criterio

    assert comparar_criterio(0.05, -0.05, 0.05) == S.IGUAL
    assert comparar_criterio(0.05, -0.03, 0.03) == S.DIFERENTE
    assert comparar_criterio(0.05, 0.0, 0.05) == S.DIFERENTE  # plano assimétrico
    assert comparar_criterio(0.05, None, 0.05) == S.DIFERENTE  # plano com um lado só
    assert comparar_criterio(None, -0.05, 0.05) == S.NAO_COMPARADO  # certificado sem critério
    assert comparar_criterio(0.05, None, None) == S.NAO_COMPARADO  # plano sem tolerância


def test_criterio_diferente_avisa_uma_vez_sem_mudar_o_parecer(tmp_path):
    from leitor_certificados.conferencia.criterio import SituacaoCriterio
    from leitor_certificados.conferencia.extracao import CertificadoLido, PontoLido

    banco = tmp_path / "planos.db"
    pontos = [{"nominal": v, "erro": 0.01, "incerteza": 0.01} for v in (0.0, 50.0, 100.0)]
    criar_banco_de_planos(banco, [{"id": "c1", "tipo": "Paquímetro", "codigo": "PQ-0001",
                                   "faixa_min": 0, "faixa_max": 100, "pontos": pontos}])
    con = sqlite3.connect(banco)
    con.execute("UPDATE pontos_plano SET tolerancia_inferior = -0.05, tolerancia_superior = 0.05")
    con.commit()
    con.close()

    def ler(criterio):
        return CertificadoLido("PQ-0001", [
            PontoLido(v, v + 0.01, 0.01, 0.01, (0, 0, 1, 1), erro_maximo=0.02, criterio=criterio)
            for v in (0.0, 50.0, 100.0)])

    planos = PlanosDQ05(banco)
    try:
        igual, diferente, sem = (conferir(ler(c), planos) for c in (0.05, 0.03, None))
    finally:
        planos.fechar()
    assert igual.resultado == diferente.resultado == sem.resultado == Resultado.APROVADO
    assert not any("critério" in a for a in igual.avisos + sem.avisos)
    avisos = [a for a in diferente.avisos if "critério" in a]
    assert avisos == ["critério de aceitação do certificado (± 0,03) diferente da tolerância "
                      "do plano (± 0,05)"]  # um aviso só para os três pontos
    assert all(p.criterio == SituacaoCriterio.DIFERENTE for p in diferente.pontos)
    assert all(p.criterio == SituacaoCriterio.IGUAL for p in igual.pontos)
