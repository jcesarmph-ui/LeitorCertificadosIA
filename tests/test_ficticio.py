"""Testes do gerador de certificados fictícios.

O gabarito precisa ser confiável: se ele disser que a data está num lugar e ela estiver em outro,
o modelo de ML aprende errado. Por isso conferimos, no próprio PDF, que cada resposta anotada
está mesmo dentro da sua caixa.
"""

import json
import random
from datetime import date

import pypdfium2 as pdfium
import pytest

from leitor_certificados.ficticio.dados import sortear_certificado
from leitor_certificados.ficticio.gerar import gerar_um, main
from leitor_certificados.ficticio.laboratorios import (
    LABORATORIOS,
    formatar_data,
    formatar_numero,
)


@pytest.fixture(scope="module")
def lote(tmp_path_factory):
    """Seis certificados gerados uma vez para todos os testes deste arquivo."""
    pasta = tmp_path_factory.mktemp("ficticios")
    gabaritos = [gerar_um(pasta, n) for n in range(1, 7)]
    return pasta, [json.loads(g.read_text(encoding="utf-8")) for g in gabaritos]


def _texto_da_pagina(caminho):
    documento = pdfium.PdfDocument(str(caminho))
    try:
        pagina = documento[0]
        return pagina, pagina.get_textpage(), documento
    except Exception:
        documento.close()
        raise


def test_formatar_numero_com_virgula_sinal_e_zero_sem_sinal():
    assert formatar_numero(1.5, 2, ",") == "1,50"
    assert formatar_numero(0.02, 2, ",", sinal_mais=True) == "+0,02"
    assert formatar_numero(-0.02, 2, ".") == "-0.02"
    assert formatar_numero(-0.0001, 2, ",", sinal_mais=True) == "0,00"


def test_formatos_de_data_dos_laboratorios():
    d = date(2026, 3, 9)
    assert formatar_data(d, "dd/mm/aaaa") == "09/03/2026"
    assert formatar_data(d, "dd.mm.aaaa") == "09.03.2026"
    assert formatar_data(d, "iso") == "2026-03-09"
    assert formatar_data(d, "extenso") == "9 de março de 2026"
    assert formatar_data(d, "dd/mmm/aaaa") == "09/mar/2026"


def test_mesma_semente_gera_o_mesmo_certificado():
    a = sortear_certificado(random.Random("2026-7"), "x")
    b = sortear_certificado(random.Random("2026-7"), "x")
    c = sortear_certificado(random.Random("2026-8"), "x")
    assert a == b
    assert a != c


def test_todos_os_laboratorios_aparecem():
    sorteados = {sortear_certificado(random.Random(f"2026-{n}"), "x").laboratorio
                 for n in range(1, 60)}
    assert sorteados == set(LABORATORIOS)


def test_pontos_coerentes():
    for n in range(1, 80):
        cert = sortear_certificado(random.Random(f"2026-{n}"), "x")
        nominais = [p.nominal for p in cert.pontos]
        assert nominais[0] == cert.faixa_min and nominais[-1] == cert.faixa_max
        assert nominais == sorted(nominais) and 4 <= len(nominais) <= 11
        for p in cert.pontos:
            assert p.erro == pytest.approx(p.encontrado - p.nominal, abs=10 ** -(cert.casas + 1))
            assert p.incerteza > 0 and p.k >= 2


def test_gera_os_tres_arquivos(lote):
    pasta, gabaritos = lote
    for g in gabaritos:
        assert g["ficticio"] is True
        assert (pasta / g["digital"]["arquivo"]).exists()
        assert (pasta / g["escaneado"]["arquivo"]).exists()


def test_cada_resposta_esta_dentro_da_sua_caixa_no_pdf_digital(lote):
    pasta, gabaritos = lote
    for g in gabaritos:
        pagina, texto, documento = _texto_da_pagina(pasta / g["digital"]["arquivo"])
        largura, altura = pagina.get_size()
        try:
            for campo in g["digital"]["campos"]:
                esq, topo, dir_, base = campo["caixa"]
                dentro = texto.get_text_bounded(
                    left=esq * largura, right=dir_ * largura,
                    top=altura - topo * altura, bottom=altura - base * altura,
                ).strip()
                assert dentro == campo["texto"], (g["semente"], campo)
        finally:
            documento.close()


def test_gabarito_tem_o_essencial_anotado(lote):
    _, gabaritos = lote
    for g in gabaritos:
        nomes = {c["campo"] for c in g["digital"]["campos"]}
        assert {"numero_certificado", "data_calibracao", "laboratorio", "codigo",
                "ponto.nominal", "ponto.encontrado", "ponto.incerteza"} <= nomes
        pontos = [c for c in g["digital"]["campos"] if c["campo"] == "ponto.nominal"]
        assert len(pontos) == len(g["certificado"]["pontos"])
        numero = next(c for c in g["digital"]["campos"] if c["campo"] == "numero_certificado")
        assert numero["texto"] == g["certificado"]["numero"]


def test_pdf_digital_avisa_que_e_ficticio(lote):
    pasta, gabaritos = lote
    _, texto, documento = _texto_da_pagina(pasta / gabaritos[0]["digital"]["arquivo"])
    try:
        assert "DOCUMENTO FICTÍCIO" in texto.get_text_range()
    finally:
        documento.close()


def test_escaneado_nao_tem_texto_e_as_caixas_ficam_na_pagina(lote):
    pasta, gabaritos = lote
    for g in gabaritos:
        _, texto, documento = _texto_da_pagina(pasta / g["escaneado"]["arquivo"])
        try:
            assert texto.get_text_range().strip() == ""  # só imagem: vai precisar de OCR
        finally:
            documento.close()
        assert abs(g["escaneado"]["angulo_graus"]) <= 1.5
        for campo in g["escaneado"]["campos"]:
            esq, topo, dir_, base = campo["caixa"]
            assert -0.01 <= esq < dir_ <= 1.01 and -0.01 <= topo < base <= 1.01


def test_caixas_do_escaneado_ficam_em_cima_do_texto(lote):
    """Dentro das caixas giradas há tinta (mais escuro que a folha em volta)."""
    pasta, gabaritos = lote
    g = max(gabaritos, key=lambda g: abs(g["escaneado"]["angulo_graus"]))  # o mais torto
    documento = pdfium.PdfDocument(str(pasta / g["escaneado"]["arquivo"]))
    try:
        imagem = documento[0].render(scale=1, grayscale=True).to_pil().convert("L")
    finally:
        documento.close()
    largura, altura = imagem.size
    folha = imagem.crop((0, int(altura * 0.85), largura, int(altura * 0.95)))  # parte vazia

    def media(regiao):
        histograma = regiao.histogram()
        return sum(i * n for i, n in enumerate(histograma)) / sum(histograma)

    for campo in g["escaneado"]["campos"]:
        esq, topo, dir_, base = campo["caixa"]
        regiao = imagem.crop((int(esq * largura), int(topo * altura),
                              int(dir_ * largura) + 1, int(base * altura) + 1))
        assert media(regiao) < media(folha) - 10, campo


def test_mesma_semente_gera_os_mesmos_arquivos(tmp_path):
    a = gerar_um(tmp_path / "a", 3)
    b = gerar_um(tmp_path / "b", 3)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    assert (tmp_path / "a" / "cert_0003_digital.pdf").read_bytes() == \
        (tmp_path / "b" / "cert_0003_digital.pdf").read_bytes()


def test_linha_de_comando_gera_o_lote(tmp_path, capsys):
    main(["--pasta", str(tmp_path), "--quantidade", "2"])
    assert len(list(tmp_path.glob("*.json"))) == 2
    assert len(list(tmp_path.glob("*.pdf"))) == 4
    assert "2 certificados fictícios" in capsys.readouterr().out


# --- laboratório no estilo das colunas "Erro Máximo" e "Critério de aceitação ±" (ADR 0009) -----

def test_laboratorio_com_erro_maximo_e_criterio():
    certs = [c for n in range(1, 120)
             if (c := sortear_certificado(random.Random(f"2026-{n}"), "x")).laboratorio
             == "rio_manso"]
    assert certs, "o laboratório novo precisa aparecer no sorteio"
    for cert in certs:
        criterios = {p.criterio for p in cert.pontos}
        assert len(criterios) == 1 and criterios.pop() > 0  # um critério para o certificado
        for p in cert.pontos:
            assert p.erro_maximo == pytest.approx(abs(p.erro) + p.incerteza,
                                                  abs=10 ** -(cert.casas + 1))
    outro = next(c for n in range(1, 120)
                 if (c := sortear_certificado(random.Random(f"2026-{n}"), "x")).laboratorio
                 != "rio_manso")
    assert all(p.criterio is None and p.erro_maximo is None for p in outro.pontos)


def test_gabarito_anota_erro_maximo_e_criterio(tmp_path):
    n = next(n for n in range(1, 120)
             if sortear_certificado(random.Random(f"2026-{n}"), "x").laboratorio == "rio_manso")
    gab = json.loads(gerar_um(tmp_path, n).read_text(encoding="utf-8"))
    campos = gab["digital"]["campos"]
    quantos = len(gab["certificado"]["pontos"])
    for campo in ("ponto.erro_maximo", "ponto.criterio", "ponto.incerteza", "ponto.k"):
        assert sum(c["campo"] == campo for c in campos) == quantos, campo
    pagina, texto, documento = _texto_da_pagina(tmp_path / gab["digital"]["arquivo"])
    try:
        tudo = texto.get_text_range()
        assert "Critério de" in tudo and "aceitação ±" in tudo and "Máximo" in tudo
        assert "critério de aceitação adotado pelo cliente: ±" in tudo
    finally:
        documento.close()


def test_gabarito_de_gerador_antigo_e_refeito(tmp_path):
    from leitor_certificados.ficticio.gerar import VERSAO_GERADOR, gabarito_atual

    caminho = gerar_um(tmp_path, 1)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["versao_gerador"] == VERSAO_GERADOR
    del dados["versao_gerador"]  # como um gabarito feito antes da versão 0.7.0
    dados["certificado"]["numero"] = "VELHO"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    refeito = json.loads(gabarito_atual(tmp_path, 1).read_text(encoding="utf-8"))
    assert refeito["versao_gerador"] == VERSAO_GERADOR
    assert refeito["certificado"]["numero"] != "VELHO"
    assert gabarito_atual(tmp_path, 1).stat().st_mtime == caminho.stat().st_mtime  # atual: fica
