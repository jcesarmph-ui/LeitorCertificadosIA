"""Testes do aprendizado com o uso: reais corrigidos à mão viram treino."""

import json

from leitor_certificados.aprendizado.correcoes import (
    carregar_marcacao,
    carregar_pasta,
    contar_correcoes,
    treinar_com_correcoes,
)
from leitor_certificados.aprendizado.modelo import prever
from leitor_certificados.leitura import Pagina, Palavra


def _pagina() -> Pagina:
    return Pagina("ocr", [
        Palavra("Padrão", (0.10, 0.30, 0.18, 0.32), 0.97),
        Palavra("2,500", (0.10, 0.40, 0.16, 0.42), 0.99),
        Palavra("5,100", (0.10, 0.45, 0.16, 0.47), 0.99),
        Palavra("Erro", (0.50, 0.30, 0.56, 0.32), 0.98),
        Palavra("0,001", (0.50, 0.40, 0.56, 0.42), 0.99),
        Palavra("0,002", (0.50, 0.45, 0.56, 0.47), 0.99),
    ], rotacao=180)


def _gravar(pasta, nome="real.palavras.json"):
    pagina = _pagina()
    palpite = ["outro", "ponto.incerteza", "ponto.incerteza", "outro", "ponto.erro", "ponto.erro"]
    certo = ["outro", "ponto.nominal", "ponto.nominal", "outro", "ponto.erro", "ponto.erro"]
    itens = [{"i": i, "texto": p.texto, "caixa": list(p.caixa), "confianca": p.confianca,
              "rotulo": r, "certeza": 0.5, "certo": c}
             for i, (p, r, c) in enumerate(zip(pagina.palavras, palpite, certo, strict=True))]
    arquivo = pasta / nome
    arquivo.write_text(json.dumps({"origem": "ocr", "rotacao": 180, "palavras": itens}),
                       encoding="utf-8")
    return arquivo, certo


def test_carregar_marcacao_devolve_pagina_e_rotulos_certos(tmp_path):
    arquivo, certo = _gravar(tmp_path)
    pagina, rotulos = carregar_marcacao(arquivo)
    assert pagina.origem == "ocr" and pagina.rotacao == 180
    assert [p.texto for p in pagina.palavras][1] == "2,500"
    assert rotulos == certo


def test_contar_correcoes_mostra_o_que_a_pessoa_mudou(tmp_path):
    arquivo, _ = _gravar(tmp_path)
    assert contar_correcoes(arquivo) == 2


def test_modelo_aprende_a_correcao(tmp_path):
    _gravar(tmp_path)
    reais = carregar_pasta(tmp_path)
    assert len(reais) == 1
    modelo = treinar_com_correcoes([], [], reais)
    pagina, certo = reais[0]
    assert [r for r, _ in prever(modelo, pagina)] == certo


def test_texto_corrigido_a_mao_entra_no_treino(tmp_path):
    arquivo, _ = _gravar(tmp_path)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["palavras"][1]["texto_certo"] = "2,800"  # o OCR leu "2,500"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    pagina, _ = carregar_marcacao(arquivo)
    assert pagina.palavras[1].texto == "2,800"
    assert pagina.palavras[2].texto == "5,100"  # sem correção: fica o que o OCR leu
