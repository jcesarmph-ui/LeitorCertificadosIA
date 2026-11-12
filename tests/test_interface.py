"""Testes da interface (etapa 5): o serviço (sem tela) e a janela em modo offscreen.

Só certificados FICTÍCIOS, gerados pelo próprio projeto numa pasta temporária. Nenhum dado real.
"""

import json
import os
import time

import pytest
from PIL import ImageChops

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from leitor_certificados import __version__  # noqa: E402
from leitor_certificados.conferencia.avaliacao import Resultado  # noqa: E402
from leitor_certificados.ficticio.gerar import gerar_um  # noqa: E402
from leitor_certificados.ficticio.plano import criar_banco_de_planos  # noqa: E402
from leitor_certificados.interface.estilo import aplicar_estilo  # noqa: E402
from leitor_certificados.interface.janela import Janela  # noqa: E402
from leitor_certificados.interface.servico import (  # noqa: E402
    ROTULOS,
    Pastas,
    Servico,
    descrever_pontos,
    descrever_tolerancia,
    gravar_correcao,
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
