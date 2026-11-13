"""Testes da leitura do PDF digital.

A prova é o gabarito da etapa 1: ele diz qual texto está em cada caixa da folha. Se a leitura
está certa, as palavras lidas dentro de cada caixa formam exatamente esse texto.
"""

import json

import pypdfium2 as pdfium
import pytest

from leitor_certificados.ficticio.gerar import gerar_um
from leitor_certificados.leitura.digital import ler_digital, tem_texto


@pytest.fixture(scope="module")
def lote(tmp_path_factory):
    """Dez certificados (passa pelos 5 laboratórios) gerados uma vez para este arquivo."""
    pasta = tmp_path_factory.mktemp("leitura")
    gabaritos = [gerar_um(pasta, n) for n in range(1, 11)]
    return pasta, [json.loads(g.read_text(encoding="utf-8")) for g in gabaritos]


def test_cada_resposta_do_gabarito_e_lida_na_sua_caixa(lote):
    pasta, gabaritos = lote
    for gabarito in gabaritos:
        (pagina,) = ler_digital(pasta / gabarito["digital"]["arquivo"])
        assert pagina.origem == "digital"
        for campo in gabarito["digital"]["campos"]:
            assert pagina.texto_na_caixa(campo["caixa"]) == campo["texto"], campo["campo"]


def test_palavras_nao_tem_espaco_e_ficam_dentro_da_pagina(lote):
    pasta, gabaritos = lote
    (pagina,) = ler_digital(pasta / gabaritos[0]["digital"]["arquivo"])
    assert len(pagina.palavras) > 50
    for palavra in pagina.palavras:
        assert palavra.texto and not any(letra.isspace() for letra in palavra.texto)
        esq, topo, dir_, base = palavra.caixa
        assert 0 <= esq < dir_ <= 1 and 0 <= topo < base <= 1
        assert palavra.confianca == 1.0


def test_colunas_da_tabela_nao_grudam(lote):
    """Dois números vizinhos na tabela são duas palavras, nunca uma só."""
    pasta, gabaritos = lote
    for gabarito in gabaritos:
        (pagina,) = ler_digital(pasta / gabarito["digital"]["arquivo"])
        nominal = next(c for c in gabarito["digital"]["campos"] if c["campo"] == "ponto.nominal")
        assert pagina.texto_na_caixa(nominal["caixa"]) == nominal["texto"]


def test_sabe_se_a_pagina_tem_texto(lote):
    pasta, gabaritos = lote
    for chave, esperado in (("digital", True), ("escaneado", False)):
        documento = pdfium.PdfDocument(str(pasta / gabaritos[0][chave]["arquivo"]))
        try:
            assert tem_texto(documento[0]) is esperado
        finally:
            documento.close()
