"""Testes da interface (etapa 5): o serviço (sem tela) e a janela em modo offscreen.

Só certificados FICTÍCIOS, gerados pelo próprio projeto numa pasta temporária. Nenhum dado real.
"""

import colorsys
import json
import os
import time

import pytest
from PIL import ImageChops

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QLabel  # noqa: E402

from leitor_certificados import __version__  # noqa: E402
from leitor_certificados.conferencia.avaliacao import Resultado  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.ficticio.plano import criar_banco_de_planos  # noqa: E402
from leitor_certificados.interface.estilo import aplicar_estilo  # noqa: E402
from leitor_certificados.interface.folha import tipo_do_rotulo  # noqa: E402
from leitor_certificados.interface.janela import Janela  # noqa: E402
from leitor_certificados.interface.legenda import icone_do_rotulo  # noqa: E402
from leitor_certificados.interface.paletas import PALETA_ATUAL, PALETAS  # noqa: E402
from leitor_certificados.interface.servico import (  # noqa: E402
    ROTULOS,
    Pastas,
    Servico,
    arquivo_de_correcoes,
    descrever_pontos,
    descrever_tolerancia,
    gravar_correcao,
    gravar_manual,
    numero,
    renderizar_folha,
)

TREINO = 25  # certificados de treino (rápido: PDF digital)


@pytest.fixture(scope="module")
def app():
    aplicacao = QApplication.instance() or QApplication([])
    filtro = aplicar_estilo(aplicacao)
    yield aplicacao
    del filtro


@pytest.fixture(scope="module")
def mundo(tmp_path_factory):
    base = tmp_path_factory.mktemp("interface")
    gabaritos = [json.loads(gerar_um(base / "fic", n).read_text(encoding="utf-8"))
                 for n in range(1, TREINO + 2)]
    criar_banco_de_planos(base / "planos.db", [g["certificado"] for g in gabaritos])
    pastas = Pastas(marcacao=base / "marcacao", ficticios=base / "fic", banco=base / "planos.db",
                    modelo=base / "modelos" / "modelo.joblib", quantidade_ficticios=TREINO)
    servico = Servico(pastas)
    assert servico.preparar_modelo() == "treinado"
    novo = base / "fic" / gabaritos[TREINO]["digital"]["arquivo"]  # o certificado nº 26
    return servico, pastas, novo


def test_modelo_fica_salvo_e_e_reaberto(mundo):
    servico, pastas, _ = mundo
    assert pastas.modelo.exists()
    outro = Servico(pastas)
    assert outro.preparar_modelo() == "salvo"  # usa o salvo, sem treinar de novo


def test_analise_acha_pontos_e_da_parecer(mundo):
    servico, _, certificado = mundo
    analise = servico.analisar(certificado)
    assert len(analise.previsoes) == len(analise.pagina.palavras) == len(analise.rotulos)
    assert analise.conferencia is not None and analise.conferencia.pontos
    assert analise.conferencia.resultado in (Resultado.APROVADO, Resultado.REPROVADO)
    assert analise.campos.get("codigo")
    linhas = descrever_pontos(analise.conferencia)
    assert len(linhas) == len(analise.conferencia.pontos)
    assert "Tolerância do plano" in linhas[0].dica() and "Erro ± U" in linhas[0].dica()


def test_sem_banco_a_conferencia_fica_de_fora_com_aviso(mundo):
    servico, pastas, certificado = mundo
    sem_banco = Servico(Pastas(marcacao=pastas.marcacao, ficticios=pastas.ficticios,
                               banco=pastas.banco.parent / "nao_existe.db",
                               modelo=pastas.modelo))
    sem_banco.modelo = servico.modelo
    analise = sem_banco.analisar(certificado)
    assert analise.conferencia is None and analise.avisos


def test_correcao_cria_arquivo_e_nao_apaga_as_anteriores(mundo):
    servico, pastas, certificado = mundo
    analise = servico.analisar(certificado)
    arquivo = pastas.marcacao / f"{certificado.stem}.palavras.json"
    assert not arquivo.exists()
    assert gravar_correcao(pastas, analise, [0, 1], "tecnico") == 2
    dados = json.loads(arquivo.read_text(encoding="utf-8"))["palavras"]
    assert len(dados) == len(analise.pagina.palavras)
    assert dados[0]["certo"] == "tecnico" and dados[1]["certo"] == "tecnico"
    assert dados[2]["certo"] == dados[2]["rotulo"]  # o resto começa igual ao palpite
    # corrigir outra palavra depois mantém as duas primeiras
    assert gravar_correcao(pastas, analise, [2], "cliente") == 1
    dados = json.loads(arquivo.read_text(encoding="utf-8"))["palavras"]
    assert [d["certo"] for d in dados[:3]] == ["tecnico", "tecnico", "cliente"]
    assert analise.corrigidas >= {0, 1, 2}
    # reabrir mostra o que foi corrigido
    de_novo = servico.analisar(certificado)
    assert de_novo.rotulos[0] == "tecnico" and 0 in de_novo.corrigidas
    with pytest.raises(ValueError):
        gravar_correcao(pastas, analise, [0], "rótulo que não existe")


def test_aprender_com_as_correcoes_salva_o_modelo(mundo):
    servico, pastas, certificado = mundo
    analise = servico.analisar(certificado)
    gravar_correcao(pastas, analise, [0], "outro")
    antes = pastas.modelo.stat().st_mtime_ns
    time.sleep(0.05)
    assert servico.aprender() >= 1  # o certificado corrigido entrou no treino
    assert pastas.modelo.stat().st_mtime_ns > antes


def test_folha_de_cabeca_para_baixo_e_virada_em_pe(mundo):
    _, _, certificado = mundo
    normal = renderizar_folha(certificado, 0)
    virada = renderizar_folha(certificado, 180)
    assert normal.size == virada.size
    assert ImageChops.difference(virada.rotate(180), normal).getbbox() is None


def test_formatacao_em_portugues():
    assert numero(0.05) == "0,05" and numero(-0.001) == "-0,001" and numero(None) == "—"
    assert numero(10.0) == "10" and numero(-0.0) == "0"
    assert descrever_tolerancia(-0.05, 0.05) == "-0,05 a +0,05"
    assert descrever_tolerancia(None, None) == "—"
    assert "Código do instrumento" in ROTULOS.values() and "outro" in ROTULOS


def esperar(app, janela, limite=120.0):
    inicio = time.time()
    while janela.ocupado and time.time() - inicio < limite:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not janela.ocupado


def test_janela_abre_analisa_em_segundo_plano_e_mostra_parecer(app, mundo):
    servico, _, certificado = mundo
    janela = Janela(servico)
    janela.show()
    assert __version__ in janela.windowTitle()
    janela.abrir(certificado)
    assert janela.ocupado  # a análise roda em outra thread
    esperar(app, janela)
    assert janela.analise is not None
    assert janela.parecer.text() in ("APROVADO", "REPROVADO", "PENDENTE")
    assert janela.tabela.rowCount() == len(janela.analise.conferencia.pontos)
    assert janela.campos["codigo"].text() not in ("—", "não encontrado")
    assert janela.botao_corrigir.isEnabled()
    janela.close()


def test_janela_corrigir_varias_palavras_conta_pendentes(app, mundo):
    servico, pastas, certificado = mundo
    janela = Janela(servico)
    janela.show()
    janela.abrir(certificado)
    esperar(app, janela)
    janela.botao_corrigir.setChecked(True)
    janela.folha.selecionar([3, 4])
    assert janela.folha._caixas[3].selecionada
    janela.aplicar_rotulo([3, 4], "fabricante")
    assert janela.analise.rotulos[3] == "fabricante"
    assert not janela.folha._caixas[3].selecionada  # a seleção some depois de aplicar
    assert "(" in janela.botao_aprender.text()  # mostra quantas correções esperam
    janela.close()


def test_janela_aprende_em_segundo_plano_e_reanalisa(app, mundo):
    servico, _, certificado = mundo
    janela = Janela(servico)
    janela.show()
    janela.abrir(certificado)
    esperar(app, janela)
    janela.aprender()
    assert janela.ocupado
    esperar(app, janela)  # aprende e reanalisa o certificado aberto
    esperar(app, janela)
    assert janela._pendentes == 0 and janela.analise is not None
    janela.close()


def test_roda_do_mouse_nao_muda_lista(app):
    combo = QComboBox()
    combo.addItems(["a", "b", "c"])
    combo.show()
    evento = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
    assert evento.type() == QEvent.Type.Wheel
    app.sendEvent(combo, evento)
    assert combo.currentIndex() == 0
    combo.close()


def test_arquivo_que_nao_e_pdf_vira_aviso_na_tela_sem_pop_up(app, mundo, tmp_path):
    servico, _, _ = mundo
    janela = Janela(servico)
    ruim = tmp_path / "ruim.pdf"
    ruim.write_text("não sou um pdf")
    janela.abrir(ruim)
    assert not janela.ocupado and "Não consegui abrir" in janela.avisos.text()
    janela.close()


# ---------------------------------------------------------------- segunda rodada de ajustes

def test_valor_digitado_a_mao_confere_na_hora_e_volta_ao_reabrir(mundo):
    servico, pastas, certificado = mundo
    analise = servico.analisar(certificado)
    codigo_lido = analise.conferencia.codigo
    gravar_manual(pastas, analise, "codigo", "ZZ-9999")  # código que não existe no cadastro
    servico.reconferir(analise)
    assert analise.conferencia.resultado == Resultado.PENDENTE
    dados = json.loads(arquivo_de_correcoes(pastas, certificado).read_text(encoding="utf-8"))
    assert dados["manual"] == {"codigo": "ZZ-9999"}
    # uma correção de rótulo depois não apaga o valor digitado
    gravar_correcao(pastas, analise, [0], analise.rotulos[0])
    dados = json.loads(arquivo_de_correcoes(pastas, certificado).read_text(encoding="utf-8"))
    assert dados["manual"] == {"codigo": "ZZ-9999"}
    reaberta = servico.analisar(certificado)
    assert reaberta.manual == {"codigo": "ZZ-9999"}
    assert reaberta.conferencia.resultado == Resultado.PENDENTE
    gravar_manual(pastas, reaberta, "codigo", codigo_lido)  # o código certo, digitado
    servico.reconferir(reaberta)
    assert reaberta.conferencia.resultado != Resultado.PENDENTE
    gravar_manual(pastas, reaberta, "codigo", "")  # vazio apaga
    assert "manual" not in json.loads(
        arquivo_de_correcoes(pastas, certificado).read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        gravar_manual(pastas, reaberta, "fabricante", "x")


def test_certeza_baixa_vira_revisar_e_o_ponto_mostra_a_certeza(mundo):
    servico, _, certificado = mundo
    analise = servico.analisar(certificado)
    campo = next(i for i, r in enumerate(analise.rotulos)
                 if r != "outro" and i not in analise.corrigidas)
    analise.previsoes[campo] = (analise.previsoes[campo][0], 0.3)
    assert analise.revisar(campo)
    analise.previsoes[campo] = (analise.previsoes[campo][0], 0.9)
    assert not analise.revisar(campo)
    linhas = descrever_pontos(analise.conferencia, analise)
    assert linhas and all(0 < c <= 1 for c in linhas[0].certezas.values())
    assert "nominal" in linhas[0].certezas


def test_paletas_nao_usam_verde_vermelho_nem_amarelo_fortes():
    for nome, opcao in PALETAS.items():
        for rgb in [*opcao.cores.values(), opcao.padrao]:
            h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            graus = h * 360
            forte = s > 0.5 and v > 0.4
            proibida = graus < 15 or graus > 345 or 45 <= graus <= 65 or 85 <= graus <= 160
            assert not (forte and proibida), f"paleta {nome}: {rgb} parece verde/vermelho/amarelo"
    assert PALETA_ATUAL in PALETAS


def _abrir_pronto(app, servico, certificado):
    janela = Janela(servico)
    janela.resize(1500, 900)
    janela.show()
    janela.abrir(certificado)
    esperar(app, janela)
    return janela


def test_botao_principal_vira_analisar_outro(app, mundo):
    servico, _, certificado = mundo
    janela = Janela(servico)
    assert janela.botao_abrir.text() == "Abrir certificado"
    janela.abrir(certificado)
    assert janela.folha.brilhando() and janela.botao_cancelar.isVisibleTo(janela)
    esperar(app, janela)
    assert not janela.folha.brilhando()
    assert janela.botao_abrir.text() == "Analisar outro"
    janela.close()


def test_cancelar_volta_ao_que_estava_e_joga_o_resultado_fora(app, mundo):
    servico, _, certificado = mundo
    janela = _abrir_pronto(app, servico, certificado)
    anterior = janela.analise
    janela.abrir(certificado)
    janela.cancelar_analise()
    assert not janela.ocupado and not janela.folha.brilhando()
    assert janela.analise is anterior and janela.parecer.text() != "—"
    for tarefa in list(janela._tarefas):  # a thread termina em segundo plano...
        tarefa.wait(60000)
    app.processEvents()
    assert janela.analise is anterior  # ...e o resultado dela é ignorado
    # cancelar sem nada antes volta para a folha vazia
    vazia = Janela(servico)
    vazia.abrir(certificado)
    vazia.cancelar_analise()
    assert vazia.analise is None and vazia.botao_abrir.text() == "Abrir certificado"
    for tarefa in list(vazia._tarefas):
        tarefa.wait(60000)
    janela.close()
    vazia.close()


def _roda(folha, ctrl: bool):
    meio = QPointF(folha.viewport().width() / 2, folha.viewport().height() / 2)
    modificador = (Qt.KeyboardModifier.ControlModifier if ctrl
                   else Qt.KeyboardModifier.NoModifier)
    return QWheelEvent(meio, folha.viewport().mapToGlobal(meio), QPoint(0, 0), QPoint(0, 120),
                       Qt.MouseButton.NoButton, modificador, Qt.ScrollPhase.NoScrollPhase, False)


def test_ctrl_roda_da_zoom_e_a_roda_sozinha_so_rola(app, mundo):
    servico, _, certificado = mundo
    janela = _abrir_pronto(app, servico, certificado)
    folha = janela.folha
    escala = folha.transform().m11()
    app.sendEvent(folha.viewport(), _roda(folha, ctrl=False))
    assert folha.transform().m11() == pytest.approx(escala)
    app.sendEvent(folha.viewport(), _roda(folha, ctrl=True))
    assert folha.transform().m11() == pytest.approx(escala * 1.15)
    janela.close()


def test_clicar_num_ponto_conferido_abre_o_quadrinho_e_esc_fecha(app, mundo):
    servico, _, certificado = mundo
    janela = _abrir_pronto(app, servico, certificado)
    folha = janela.folha
    folha.centerOn(folha._zonas[0].rect().center())
    app.processEvents()
    local = folha.mapFromScene(folha._zonas[0].rect().center())
    QTest.mouseClick(folha.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, local)
    app.processEvents()
    assert janela.quadro is not None and janela.quadro.isVisible()
    textos = " ".join(w.text() for w in janela.quadro.findChildren(QLabel))
    assert "Certeza do modelo" in textos and "Tolerância do plano" in textos
    QTest.keyClick(janela.quadro, Qt.Key.Key_Escape)
    app.processEvents()
    assert janela.quadro is None or not janela.quadro.isVisible()
    # clicar fora de um ponto conferido não abre nada
    QTest.mouseClick(folha.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(3, 3))
    app.processEvents()
    assert janela.quadro is None or not janela.quadro.isVisible()
    janela.close()


def test_sem_legenda_e_a_dica_do_mouse_diz_o_tipo_do_valor(app, mundo):
    servico, _, certificado = mundo
    janela = _abrir_pronto(app, servico, certificado)
    assert not hasattr(janela, "legenda")  # tudo azul: a legenda saiu
    assert all(not icone_do_rotulo(r).isNull() for r in ROTULOS)
    dicas = {c.toolTip().splitlines()[0] for c in janela.folha._caixas
             if janela.analise.rotulos[c.indice].startswith("ponto.")}
    assert {"VALOR NOMINAL", "ERRO", "INCERTEZA (U)"} <= dicas
    assert tipo_do_rotulo("ponto.k") == "K" and tipo_do_rotulo("ponto.erro") == "ERRO"
    # a área do ponto não tem dica própria (senão esconderia a dica de cada número)
    assert all(not z.toolTip() for z in janela.folha._zonas)
    janela.close()


def test_temas_tem_as_cores_que_o_estilo_usa():
    from leitor_certificados.interface import estilo
    for chave in estilo.TEMAS:
        assert "background" in estilo.montar_estilo(chave)
    assert estilo.TEMA_ATUAL in estilo.TEMAS and estilo.TEMA_ATUAL != "preto"


def test_digitar_codigo_na_tela_mostra_digitado(app, mundo):
    servico, _, certificado = mundo
    janela = _abrir_pronto(app, servico, certificado)
    janela.botao_corrigir.setChecked(True)
    assert janela.faixa_manual.isVisibleTo(janela)
    janela.valor_manual.setText("BAL-005")
    janela.usar_valor_manual()
    assert janela.campos["codigo"].text() == "BAL-005 (digitado)"
    assert janela.parecer.text() == "PENDENTE"  # código desconhecido: pendente, nunca aprovado
    janela.valor_manual.setText("")
    janela.usar_valor_manual()  # apaga: volta ao que o modelo leu
    assert "(digitado)" not in janela.campos["codigo"].text()
    janela.close()
