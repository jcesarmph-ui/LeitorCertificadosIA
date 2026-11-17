"""Testes da etapa 8: validade dos padrões no dia da calibração (ADR 0010).

Regras do usuário: validade "07/2026" vale o mês inteiro; padrão vencido → parecer PENDENTE
se os pontos passam, REPROVADO continua REPROVADO (sempre com o motivo, em vermelho); validade
não lida → só aviso amarelo. Só dados fictícios.
"""

import json
import sqlite3
from datetime import date

import pytest

from leitor_certificados.aprendizado.modelo import treinar
from leitor_certificados.conferencia.avaliacao import Resultado
from leitor_certificados.conferencia.conferir import conferir
from leitor_certificados.conferencia.extracao import (
    CertificadoLido,
    PadraoLido,
    PontoLido,
    montar_certificado,
    montar_padroes,
)
from leitor_certificados.conferencia.padroes import (
    SituacaoPadrao,
    conferir_padroes,
    ler_data,
    ler_validade,
)
from leitor_certificados.conferencia.plano import PlanosDQ05
from leitor_certificados.ficticio.dados import sortear_certificado
from leitor_certificados.ficticio.gerar import gerar_um
from leitor_certificados.ficticio.laboratorios import LABORATORIOS
from leitor_certificados.ficticio.plano import criar_banco_de_planos
from leitor_certificados.leitura import Pagina, Palavra
from leitor_certificados.leitura.ler import ler_pdf

# --- datas escritas de vários jeitos ------------------------------------------------------------


@pytest.mark.parametrize("texto", [
    "12/08/2026", "12.08.2026", "2026-08-12", "12 de agosto de 2026", "12/ago/2026",
    "12-08-26", "Data: 12/08/2026", "12/08/2026 13/08/2026",
])
def test_ler_data_em_todos_os_formatos(texto):
    assert ler_data(texto) == date(2026, 8, 12)


def test_ler_data_bilingue_e_texto_que_nao_e_data():
    assert ler_data("17-11-25/11-17-25") == date(2025, 11, 17)  # vale a primeira
    assert ler_data("31/02/2026") is None  # dia que não existe
    assert ler_data("08/2027") is None  # só mês e ano não é data completa
    assert ler_data("") is None and ler_data(None) is None


def test_validade_so_com_mes_vale_o_mes_inteiro():
    validade = ler_validade("07/2026")
    assert validade.ate == date(2026, 7, 31) and validade.so_mes
    assert ler_validade("02/2028").ate == date(2028, 2, 29)  # ano bissexto
    completa = ler_validade("23/12/2026")
    assert completa.ate == date(2026, 12, 23) and not completa.so_mes
    assert ler_validade("13/2026") is None and ler_validade("Não Consta") is None


# --- a regra ------------------------------------------------------------------------------------

def test_padrao_do_proprio_mes_esta_em_dia_e_do_mes_anterior_vencido():
    r = conferir_padroes([("P-1", "07/2026", None), ("P-2", "06/2026", None)], "20/07/2026")
    assert [p.situacao for p in r.padroes] == [SituacaoPadrao.EM_DIA, SituacaoPadrao.VENCIDO]
    assert r.algum_vencido and not r.avisos
    assert r.erros == ["padrão P-2 vencido: validade até 30/06/2026, calibração em 20/07/2026"]


def test_validade_no_proprio_dia_ainda_vale():
    r = conferir_padroes([("P-1", "20/07/2026", None)], "20/07/2026")
    assert r.padroes[0].situacao == SituacaoPadrao.EM_DIA and not r.avisos and not r.erros


def test_validade_ou_data_nao_lida_so_avisa():
    sem_validade = conferir_padroes([("P-1", None, None)], "20/07/2026")
    assert sem_validade.padroes[0].situacao == SituacaoPadrao.NAO_CONFERIDO
    assert sem_validade.avisos == ["padrão P-1: validade não encontrada"]
    sem_data = conferir_padroes([("P-1", "07/2026", None)], None)
    assert sem_data.padroes[0].situacao == SituacaoPadrao.NAO_CONFERIDO
    assert sem_data.avisos == ["data da calibração não encontrada: validade dos padrões não "
                               "conferida"]
    nenhum = conferir_padroes([], "20/07/2026")
    assert nenhum.avisos == ["padrões não encontrados no certificado: validade dos padrões não "
                             "conferida"]
    assert not (sem_validade.algum_vencido or sem_data.algum_vencido or nenhum.algum_vencido)


def test_padrao_vencido_deixa_pendente_o_aprovado_e_reprovado_continua(tmp_path):
    banco = tmp_path / "planos.db"
    pontos = [{"nominal": v, "erro": 0.0, "incerteza": 0.01} for v in (0.0, 50.0)]
    criar_banco_de_planos(banco, [{"id": "c1", "tipo": "Paquímetro", "codigo": "PQ-0001",
                                   "faixa_min": 0, "faixa_max": 50, "pontos": pontos}])
    con = sqlite3.connect(banco)  # tolerância folgada: sem padrão vencido, o parecer aprova
    con.execute("UPDATE pontos_plano SET tolerancia_inferior = -0.05, tolerancia_superior = 0.05")
    con.commit()
    con.close()
    lidos = [PontoLido(v, v, 0.0, 0.01, (0, 0, 1, 1)) for v in (0.0, 50.0)]
    fora = [PontoLido(0.0, 0.0, 0.0, 0.01, (0, 0, 1, 1)),
            PontoLido(50.0, 50.1, 0.1, 0.01, (0, 0, 1, 1))]  # 0,1 + 0,01 passa de 0,05

    def com(padroes, data="20/07/2026", pontos=lidos):
        return CertificadoLido("PQ-0001", pontos, data_calibracao=data, padroes=tuple(
            PadraoLido(c, v, (0, 0, 1, 1)) for c, v in padroes))

    planos = PlanosDQ05(banco)
    try:
        em_dia = conferir(com([("P-1", "07/2026")]), planos)
        vencido = conferir(com([("P-1", "07/2026"), ("P-2", "06/2026")]), planos)
        sem_tabela = conferir(com([]), planos)
        sem_data = conferir(com([("P-1", "06/2026")], data=None), planos)
        reprovado = conferir(com([("P-2", "06/2026")], pontos=fora), planos)
        reprovado_sem_validade = conferir(com([("P-1", None)], pontos=fora), planos)
    finally:
        planos.fechar()
    assert em_dia.resultado == Resultado.APROVADO and not em_dia.avisos and not em_dia.erros
    assert vencido.resultado == Resultado.PENDENTE
    assert vencido.erros == ["padrão P-2 vencido: validade até 30/06/2026, calibração em "
                             "20/07/2026 — parecer pendente (os pontos passam, mas o padrão "
                             "estava vencido)"]
    # pontos fora + padrão vencido: continua REPROVADO, com os dois motivos em vermelho
    assert reprovado.resultado == Resultado.REPROVADO
    assert reprovado.erros == [
        "1 ponto(s) fora da tolerância: 50",
        "padrão P-2 vencido: validade até 30/06/2026, calibração em 20/07/2026 — o parecer "
        "continua reprovado pelos pontos"]
    # não lido (decisão do usuário, 2026-11-16): aviso amarelo e parecer PENDENTE
    assert sem_tabela.resultado == sem_data.resultado == Resultado.PENDENTE
    assert sem_tabela.avisos and sem_data.avisos
    assert any("não foi conferida" in a for a in sem_tabela.avisos + sem_data.avisos)
    # não lido + pontos fora: continua REPROVADO
    assert reprovado_sem_validade.resultado == Resultado.REPROVADO
    assert not (sem_tabela.erros or sem_data.erros)


# --- montar os padrões a partir das palavras marcadas ------------------------------------------

def _palavra(texto, x, y):
    return Palavra(texto, (x, y, x + 0.05, y + 0.01), 1.0)


def test_montar_padroes_junta_cada_linha_e_separa_dois_lado_a_lado():
    palavras = [
        _palavra("LAF-01-084", 0.1, 0.30), _palavra("Bloco", 0.3, 0.30),
        _palavra("04/2027", 0.8, 0.30),
        _palavra("A-1", 0.1, 0.32), _palavra("12", 0.2, 0.32), _palavra("de", 0.25, 0.32),
        _palavra("maio", 0.3, 0.32), _palavra("de", 0.35, 0.32), _palavra("2027", 0.4, 0.32),
        _palavra("B-2", 0.6, 0.32), _palavra("01/2028", 0.8, 0.32),
    ]
    rotulos = ["padrao.codigo", "outro", "padrao.validade",
               "padrao.codigo"] + ["padrao.validade"] * 5 + ["padrao.codigo", "padrao.validade"]
    padroes = montar_padroes(Pagina("digital", palavras), rotulos)
    assert [(p.codigo, p.validade) for p in padroes] == [
        ("LAF-01-084", "04/2027"), ("A-1", "12 de maio de 2027"), ("B-2", "01/2028")]


# --- gerador fictício ---------------------------------------------------------------------------

def test_todo_laboratorio_ficticio_tem_padroes_e_o_vencido_bate_com_a_regra():
    import random

    vistos, vencidos = set(), 0
    for n in range(300):
        cert = sortear_certificado(random.Random(f"padroes-{n}"), f"c{n}")
        assert 1 <= len(cert.padroes) <= 5
        vistos.add(cert.laboratorio)
        for p in cert.padroes:
            assert p.vencido == (p.validade_ate < cert.data_calibracao)
            vencidos += p.vencido
    assert vistos == set(LABORATORIOS)
    assert 10 <= vencidos <= 80  # ~12 % dos certificados têm um vencido


def test_gabarito_anota_codigo_e_validade_de_cada_padrao(tmp_path):
    for n in range(1, 13):
        gab = json.loads(gerar_um(tmp_path, n).read_text(encoding="utf-8"))
        quantos = len(gab["certificado"]["padroes"])
        campos = gab["digital"]["campos"]
        for campo in ("padrao.codigo", "padrao.validade"):
            marcados = [c for c in campos if c["campo"] == campo]
            assert sorted(c["padrao"] for c in marcados) == list(range(quantos)), campo
        validades = [c["texto"] for c in campos if c["campo"] == "padrao.validade"]
        for texto, padrao in zip(validades, gab["certificado"]["padroes"], strict=True):
            assert ler_validade(texto).ate == date.fromisoformat(padrao["validade_ate"])


# --- de ponta a ponta: o modelo aprende a achar os padrões -------------------------------------

def test_modelo_acha_os_padroes_em_certificados_novos(tmp_path):
    gabaritos = [json.loads(gerar_um(tmp_path, n).read_text(encoding="utf-8"))
                 for n in range(1, 46)]
    paginas = [ler_pdf(tmp_path / g["digital"]["arquivo"])[0] for g in gabaritos]
    modelo = treinar(paginas[:35], [g["digital"]["campos"] for g in gabaritos[:35]])
    certos = total = 0
    for pagina, gab in zip(paginas[35:], gabaritos[35:], strict=True):
        lido = montar_certificado(modelo, pagina)
        esperado = gab["certificado"]
        r = conferir_padroes([(p.codigo, p.validade, p.caixa) for p in lido.padroes],
                             lido.data_calibracao)
        situacoes = [p["vencido"] for p in esperado["padroes"]]
        total += 1
        certos += (len(r.padroes) == len(situacoes) and r.data_calibracao is not None
                   and [p.situacao == SituacaoPadrao.VENCIDO for p in r.padroes] == situacoes)
    assert certos >= 8, f"{certos} de {total} certificados com os padrões certos"


def test_padroes_calibrados_tira_o_pendente_mas_nao_esconde_o_vencido(tmp_path):
    """Botão "PADRÕES CALIBRADOS" (pedido do usuário, 2026-11-17): os padrões vêm em outro
    certificado. A falta da validade deixa de deixar pendente; padrão vencido continua."""
    banco = tmp_path / "planos.db"
    pontos = [{"nominal": v, "erro": 0.0, "incerteza": 0.01} for v in (0.0, 50.0)]
    criar_banco_de_planos(banco, [{"id": "c1", "tipo": "Paquímetro", "codigo": "PQ-0001",
                                   "faixa_min": 0, "faixa_max": 50, "pontos": pontos}])
    con = sqlite3.connect(banco)
    con.execute("UPDATE pontos_plano SET tolerancia_inferior = -0.05, tolerancia_superior = 0.05")
    con.commit()
    con.close()
    lidos = [PontoLido(v, v, 0.0, 0.01, (0, 0, 1, 1)) for v in (0.0, 50.0)]

    def com(padroes):
        return CertificadoLido("PQ-0001", lidos, data_calibracao="20/07/2026", padroes=tuple(
            PadraoLido(c, v, (0, 0, 1, 1)) for c, v in padroes))

    planos = PlanosDQ05(banco)
    try:
        sem_tabela = conferir(com([]), planos)
        marcado = conferir(com([]), planos, padroes_calibrados=True)
        vencido = conferir(com([("P-2", "06/2026")]), planos, padroes_calibrados=True)
    finally:
        planos.fechar()
    assert sem_tabela.resultado == Resultado.PENDENTE
    assert marcado.resultado == Resultado.APROVADO and not marcado.avisos
    assert vencido.resultado == Resultado.PENDENTE and vencido.erros


# ---------------------------------------------------------------- tabela por regra (2026-11-17)

def test_validade_com_mes_pelo_nome_e_ano_curto():
    from leitor_certificados.conferencia.padroes import ler_validade

    assert str(ler_validade("fev/30").ate) == "2030-02-28"
    assert str(ler_validade("set/29").ate) == "2029-09-30"
    assert str(ler_validade("02/30").ate) == "2030-02-28"
    assert ler_validade("100") is None


def _linha(y, textos_x):
    from leitor_certificados.leitura.palavra import Palavra

    return [Palavra(t, (x, y, x + 0.05, y + 0.01)) for t, x in textos_x]


def test_tabela_conta_os_padroes_e_pega_a_validade_de_cada_um():
    from leitor_certificados.conferencia.tabela_padroes import ler_tabela_padroes
    from leitor_certificados.leitura import Pagina

    colunas = [0.05, 0.25, 0.40, 0.55, 0.70, 0.85]
    cab = ["Descrição", "Modelo", "Certificado", "Rastreabilidade", "Identificação", "Validade"]
    palavras = _linha(0.18, zip(cab, colunas, strict=True))
    palavras += _linha(0.195, [("Description", 0.05), ("Validity", 0.85), ("Model", 0.25)])
    y = 0.22
    for validade in ["fev/30", "mai/30", "set/29"]:
        palavras += _linha(y, [("Bloco", 0.05), ("HT", 0.25), ("123", 0.40), ("RBC", 0.55),
                               ("PR-1", 0.70), (validade, 0.85)])
        palavras += _linha(y + 0.011, [("Hardness", 0.05)])  # a descrição em inglês
        y += 0.022
    palavras += _linha(y + 0.06, [("INFORMAÇÕES", 0.30), ("DA", 0.40), ("CALIBRAÇÃO", 0.55)])
    tabela = ler_tabela_padroes(Pagina("digital", palavras))
    assert [v for v, _ in tabela] == ["fev/30", "mai/30", "set/29"]  # 3 padrões, sem o resto


def test_validade_do_certificado_com_dois_pontos_nao_e_tabela():
    from leitor_certificados.conferencia.tabela_padroes import ler_tabela_padroes
    from leitor_certificados.leitura import Pagina

    palavras = _linha(0.1, [("Validade:", 0.1), ("12/2027", 0.2)])
    assert ler_tabela_padroes(Pagina("digital", palavras)) is None
