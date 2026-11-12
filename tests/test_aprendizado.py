"""Testes da etapa 3: rótulos, pistas e o modelo de machine learning.

O modelo é treinado com poucos certificados fictícios (rápido) e medido em outros, que ele nunca
viu. O mínimo exigido é folgado de propósito: o número de verdade fica no README.
"""

import json

import pytest

from leitor_certificados.aprendizado.atributos import atributos_da_pagina
from leitor_certificados.aprendizado.modelo import ler_campos, prever, treinar
from leitor_certificados.aprendizado.rotulos import OUTRO, rotular
from leitor_certificados.ficticio.gerar import gerar_um
from leitor_certificados.leitura import Pagina, Palavra
from leitor_certificados.leitura.ler import ler_pdf


def _pagina_pequena() -> Pagina:
    return Pagina("digital", [
        Palavra("Número", (0.10, 0.10, 0.18, 0.12)),
        Palavra("BS", (0.19, 0.10, 0.22, 0.12)),
        Palavra("20255570", (0.23, 0.10, 0.32, 0.12)),
        Palavra("Medido", (0.50, 0.30, 0.58, 0.32)),
        Palavra("2,001", (0.50, 0.40, 0.56, 0.42)),
    ])


def test_rotular_usa_o_centro_da_palavra_na_caixa():
    campos = [{"campo": "numero_certificado", "caixa": [0.185, 0.095, 0.33, 0.125]}]
    assert rotular(_pagina_pequena(), campos) == [
        OUTRO, "numero_certificado", "numero_certificado", OUTRO, OUTRO]


def test_atributos_descrevem_o_jeito_e_o_vizinho():
    pistas = atributos_da_pagina(_pagina_pequena())
    numero = pistas[2]  # "20255570"
    assert numero["frac_digitos"] == 1.0
    assert numero["esq1=bs"] == 1.0 and numero["esq2=numero"] == 1.0
    valor = pistas[4]  # "2,001": o título da coluna está em cima, sem ligar para o lugar exato
    assert valor["tem_virgula"] == 1.0 and valor["acima1=medido"] == 1.0
    assert "acima1=NADA" in pistas[0]


@pytest.fixture(scope="module")
def lote(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("aprendizado")
    itens = []
    for n in range(1, 41):
        gab = json.loads(gerar_um(pasta, n).read_text(encoding="utf-8"))
        (pagina,) = ler_pdf(pasta / gab["digital"]["arquivo"])
        itens.append((pagina, gab["digital"]["campos"]))
    return itens


def test_modelo_acha_os_campos_em_certificados_novos(lote):
    treino, teste = lote[:32], lote[32:]
    modelo = treinar([p for p, _ in treino], [c for _, c in treino])
    certas = total = 0
    for pagina, campos in teste:
        for esperado, (previsto, certeza) in zip(rotular(pagina, campos), prever(modelo, pagina),
                                                 strict=True):
            total += 1
            certas += esperado == previsto
            assert 0 < certeza <= 1
    assert certas / total >= 0.95, f"{certas} de {total}"


def test_ler_campos_junta_as_palavras_de_cada_campo(lote):
    treino, teste = lote[:32], lote[32:]
    modelo = treinar([p for p, _ in treino], [c for _, c in treino])
    pagina, campos = teste[0]
    lidos = ler_campos(modelo, pagina)
    esperado = next(c["texto"] for c in campos if c["campo"] == "numero_certificado")
    assert "".join(lidos["numero_certificado"].split()) == "".join(esperado.split())
    assert lidos["ponto.erro"].count("|") >= 3  # uma linha de valores por ponto da tabela


def test_limiar_de_certeza_tira_palavra_incerta_dos_campos():
    from leitor_certificados.aprendizado.modelo import com_limiar

    previsoes = [("ponto.erro", 0.95), ("codigo", 0.30), (OUTRO, 0.20), ("faixa", 0.50)]
    assert com_limiar(previsoes, 0.5) == [
        ("ponto.erro", 0.95), (OUTRO, 0.30), (OUTRO, 0.20), ("faixa", 0.50)]
    assert com_limiar(previsoes, 0.0) == previsoes  # limiar 0 = sem limiar
