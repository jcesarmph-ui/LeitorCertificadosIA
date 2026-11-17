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


def _padrao_em_dia():
    from leitor_certificados.conferencia.extracao import PadraoLido
    return {"data_calibracao": "20/07/2026",
            "padroes": (PadraoLido("P-1", "07/2026", (0, 0, 1, 1)),)}


PADRAO_EM_DIA = _padrao_em_dia()  # sem padrão conferido o parecer fica pendente


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
            for v in (0.0, 50.0, 100.0)], **PADRAO_EM_DIA)

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


# --- "Erro ± U" igual ao programa de calibração (pedido do usuário, 2026-11-13) -----------------

def test_erro_com_incerteza_fica_do_lado_mais_perto_da_tolerancia():
    from leitor_certificados.conferencia.avaliacao import erro_com_incerteza

    tol = {"tolerancia_inferior": -5.0, "tolerancia_superior": 5.0}
    assert erro_com_incerteza(-1.0, 1.0, **tol).valor == -2.0  # e não 0
    assert erro_com_incerteza(1.0, 1.0, **tol).valor == 2.0
    zero = erro_com_incerteza(0.0, 1.0, **tol)
    assert zero.dos_dois_lados and zero.valor == 1.0  # "± 1"
    # tolerância assimétrica: o lado que chega mais perto do limite
    assert erro_com_incerteza(0.0, 1.0, tolerancia_inferior=-2.0,
                              tolerancia_superior=5.0).valor == -1.0
    assert erro_com_incerteza(0.5, 0.2, **tol, sem_incerteza=True).valor == 0.5
    assert erro_com_incerteza(0.5, None, **tol) is None  # U ausente nunca vale zero
    assert erro_com_incerteza(None, 0.1, **tol) is None


def test_nominal_repetido_no_plano_e_casado_na_ordem(tmp_path):
    """Goniômetro: 0° e 90° aparecem uma vez por quadrante; cada um casa com o seu do plano."""
    from leitor_certificados.conferencia.extracao import CertificadoLido, PontoLido

    nominais = (0.0, 90.0, 0.0, 90.0, 0.0)
    banco = tmp_path / "planos.db"
    criar_banco_de_planos(banco, [{
        "id": "g", "tipo": "Goniômetro", "codigo": "GN-0001", "faixa_min": 0, "faixa_max": 360,
        "pontos": [{"nominal": v, "erro": 0.0, "incerteza": 0.07} for v in nominais]}])
    con = sqlite3.connect(banco)
    con.execute("UPDATE pontos_plano SET tolerancia_inferior = -0.25, tolerancia_superior = 0.25")
    con.commit()
    con.close()
    lido = CertificadoLido("GN-0001", [PontoLido(v, v + 0.05, 0.05, 0.07, (0, 0, 1, 1))
                                       for v in nominais], **PADRAO_EM_DIA)
    planos = PlanosDQ05(banco)
    try:
        resultado = conferir(lido, planos)
    finally:
        planos.fechar()
    assert not any("não está" in a for a in resultado.avisos), resultado.avisos
    assert resultado.resultado == Resultado.APROVADO


def test_dois_numeros_com_o_mesmo_rotulo_vale_o_de_mais_certeza():
    from leitor_certificados.conferencia.extracao import _valor_da_coluna

    assert _valor_da_coluna([("7,941", 0.58), ("0,004", 1.0)]) == "0,004"
    assert _valor_da_coluna([("1", 0.9), ("350,00", 0.9)]) == "1 350,00"  # número em pedaços
    assert _valor_da_coluna([("0,07", 0.99)]) == "0,07"


def test_dois_nominais_na_linha_vale_o_que_esta_no_plano(tmp_path):
    from leitor_certificados.conferencia.extracao import CertificadoLido, PontoLido

    banco = tmp_path / "planos.db"
    criar_banco_de_planos(banco, [{
        "id": "g", "tipo": "Goniômetro", "codigo": "GN-0001", "faixa_min": 0, "faixa_max": 90,
        "pontos": [{"nominal": 30.0, "erro": 0.05, "incerteza": 0.07}]}])
    lido = CertificadoLido("GN-0001", [PontoLido(29.95, None, 0.05, 0.07, (0, 0, 1, 1),
                                                 nominais=(30.0, 29.95))])
    planos = PlanosDQ05(banco)
    try:
        resultado = conferir(lido, planos)
    finally:
        planos.fechar()
    assert resultado.pontos[0].lido.nominal == 30.0
    assert not any("não está" in a for a in resultado.avisos), resultado.avisos


# --- comparador cadastro × certificado do painel Instrumento (pedido do usuário, 2026-11-13) ---

def test_comparador_do_cadastro_so_informa():
    from leitor_certificados.conferencia.cadastro import Bate, comparar_campo, comparar_com_cadastro

    assert comparar_campo("codigo", "PAQ-016", "paq 016") == Bate.SIM
    assert comparar_campo("tipo", "Paquímetro", "Paquímetro Digital") == Bate.SIM  # um contém
    assert comparar_campo("tipo", "Paquímetro", "PAQUIMETRO") == Bate.SIM  # sem acento/maiúscula
    # OCR leu fora de ordem: as mesmas palavras batem
    assert comparar_campo("tipo", "Micrômetro externo", "externo Micrômetro") == Bate.SIM
    assert comparar_campo("tipo", "Válvula de segurança", "bar") == Bate.NAO
    assert comparar_campo("fabricante", "Digimess", "Digimes") == Bate.NAO  # uma letra: avisa
    assert comparar_campo("faixa", "0-500", "0 mm | 500 mm") == Bate.SIM
    assert comparar_campo("faixa", "7,5 bar", "8 kgf/cm²") == Bate.NAO
    assert comparar_campo("resolucao", "0,01", "0.01 mm") == Bate.SIM
    assert comparar_campo("resolucao", "0,01", "0,02 mm") == Bate.NAO
    assert comparar_campo("fabricante", "-", "Digimess") == Bate.SEM_DADO  # cadastro sem dado
    assert comparar_campo("fabricante", "Digimess", None) == Bate.SEM_DADO
    itens = comparar_com_cadastro({"codigo": "PAQ-016"}, {"codigo": "PAQ-016"})
    assert [i.chave for i in itens] == ["codigo", "tipo", "fabricante", "faixa", "resolucao"]


def test_plano_traz_o_cadastro_do_instrumento(mundo):
    _, _, gabaritos, banco, _ = mundo
    cert = gabaritos[0]["certificado"]
    planos = PlanosDQ05(banco)
    try:
        plano = planos.plano_do_instrumento(cert["codigo"])
    finally:
        planos.fechar()
    assert plano.cadastro["tipo"] == cert["tipo"]
    assert plano.cadastro["fabricante"] == cert["fabricante"]
    assert plano.cadastro["codigo"] == cert["codigo"]


# --- conferência de conta (decisão do usuário, 2026-11-16) ---------------------------------------

def _goniometro(tmp_path, linhas):
    """Plano de goniômetro ± 0,25 e certificado com a coluna Erro Máximo."""
    from leitor_certificados.conferencia.extracao import CertificadoLido, PontoLido

    banco = tmp_path / "planos.db"
    criar_banco_de_planos(banco, [{
        "id": "g", "tipo": "Goniômetro", "codigo": "GN-0001", "faixa_min": 0, "faixa_max": 360,
        "pontos": [{"nominal": n, "erro": 0.0, "incerteza": 0.07} for n, *_ in linhas]}])
    con = sqlite3.connect(banco)
    con.execute("UPDATE pontos_plano SET tolerancia_inferior = -0.25, tolerancia_superior = 0.25")
    con.commit()
    con.close()
    lido = CertificadoLido("GN-0001", [
        PontoLido(n, enc, erro, u, (0, 0, 1, 1), numeros, erro_maximo=em, criterio=0.25)
        for n, enc, erro, u, em, numeros in linhas], **PADRAO_EM_DIA)
    planos = PlanosDQ05(banco)
    try:
        return conferir(lido, planos)
    finally:
        planos.fechar()


def test_erro_escrito_como_nominal_menos_encontrado_e_aceito(tmp_path):
    """Goniômetro real: Instrumento 15,00, Padrão 15,07, Erro −0,07 (Instrumento − Padrão).
    Antes isso virava "colunas trocadas" e o programa escolhia o Quadrante como erro."""
    numeros = (15.0, 15.07, -0.07, 0.07, 2.0, 2.0, 0.14, 0.25)
    resultado = _goniometro(tmp_path, [(15.0, 15.07, -0.07, 0.07, 0.14, numeros)])
    assert resultado.resultado == Resultado.APROVADO, resultado.avisos
    assert resultado.pontos[0].erro == -0.07
    assert not any("conta" in a for a in resultado.avisos)


def test_numeros_que_nao_fecham_a_conta_nao_sao_avaliados(tmp_path):
    """O modelo pôs o Quadrante (2) no lugar do erro: |2| + 0,07 ≠ 0,12 e nenhuma troca de
    colunas fecha a conta → não avaliado (PENDENTE), nunca REPROVADO."""
    numeros = (0.0, 2.0, 2.0, 0.07, 0.12, 0.25)
    resultado = _goniometro(tmp_path, [(0.0, 2.0, 2.0, 0.07, 0.12, numeros)])
    assert resultado.resultado == Resultado.PENDENTE
    assert resultado.pontos[0].avaliacao.resultado == Resultado.NAO_AVALIADO
    assert any("não fecham a conta" in a for a in resultado.avisos)


def test_angulo_em_graus_e_minutos_vira_graus_decimais():
    """Goniômetro: "14°59'" é 14 graus e 59 minutos (decisão do usuário, 2026-11-16)."""
    from leitor_certificados.conferencia.extracao import para_numero

    assert para_numero("90°00'") == 90.0
    assert abs(para_numero("14°59'") - (14 + 59 / 60)) < 1e-8
    assert abs(para_numero("-0°01'") + 1 / 60) < 1e-8
    assert abs(para_numero("0°04'") - 4 / 60) < 1e-8
    assert para_numero("90°") is None  # sem os minutos não é o formato do goniômetro


def test_codigo_com_menos_zeros_acha_o_instrumento(tmp_path):
    """"GON-02" no certificado acha "GON-002" do cadastro (decisão do usuário, 2026-11-16), mas
    só quando não há dois instrumentos possíveis."""
    banco = tmp_path / "planos.db"
    pontos = [{"nominal": 0.0, "erro": 0.0, "incerteza": 0.07}]
    criar_banco_de_planos(banco, [
        {"id": "a", "tipo": "Goniômetro", "codigo": "GON-002", "faixa_min": 0, "faixa_max": 360,
         "pontos": pontos},
        {"id": "b", "tipo": "Paquímetro", "codigo": "PAQ-007", "faixa_min": 0, "faixa_max": 150,
         "pontos": pontos},
        {"id": "c", "tipo": "Paquímetro", "codigo": "PAQ-0007", "faixa_min": 0, "faixa_max": 150,
         "pontos": pontos}])
    planos = PlanosDQ05(banco)
    try:
        assert planos.conhece("GON-02") and planos.plano_do_instrumento("GON-02") is not None
        assert not planos.conhece("GON-20")
        assert not planos.conhece("PAQ-7")  # dois possíveis: não escolhe
    finally:
        planos.fechar()


def test_duvida_entre_instrumentos_desempata_pelos_pontos_do_plano(tmp_path):
    """"PAQ-7" pode ser PAQ-007 ou PAQ-0007: vale o único cujo plano tem os pontos do
    certificado (ideia do usuário, 2026-11-16); se os dois servem, fica pendente."""
    from leitor_certificados.conferencia.extracao import CertificadoLido, PontoLido

    banco = tmp_path / "planos.db"
    criar_banco_de_planos(banco, [
        {"id": "b", "tipo": "Paquímetro", "codigo": "PAQ-007", "faixa_min": 0, "faixa_max": 150,
         "pontos": [{"nominal": v, "erro": 0.0, "incerteza": 0.01} for v in (0.0, 50.0, 150.0)]},
        {"id": "c", "tipo": "Paquímetro", "codigo": "PAQ-0007", "faixa_min": 0, "faixa_max": 300,
         "pontos": [{"nominal": v, "erro": 0.0, "incerteza": 0.01} for v in (0.0, 100.0, 300.0)]}])

    def ler(nominais):
        return CertificadoLido("PAQ-7", [PontoLido(v, v, 0.0, 0.01, (0, 0, 1, 1))
                                         for v in nominais], **PADRAO_EM_DIA)

    planos = PlanosDQ05(banco)
    try:
        assert conferir(ler((0.0, 100.0, 300.0)), planos).codigo == "PAQ0007"
        assert conferir(ler((0.0, 50.0, 150.0)), planos).codigo == "PAQ007"
        assert conferir(ler((0.0,)), planos).resultado == Resultado.PENDENTE  # os dois servem
    finally:
        planos.fechar()


def test_goniometro_aparece_em_graus_e_minutos_na_tela():
    """Pedido do usuário (2026-11-16): ver 90°00', erro 0°04' — igual ao certificado."""
    from leitor_certificados.interface.servico import graus_minutos

    assert graus_minutos(90.0) == "90°00'"
    assert graus_minutos(4 / 60) == "0°04'"
    assert graus_minutos(-1 / 60) == "-0°01'"
    assert graus_minutos(14 + 59 / 60) == "14°59'"
    assert graus_minutos(0.0) == "0°00'" and graus_minutos(None) == "—"
