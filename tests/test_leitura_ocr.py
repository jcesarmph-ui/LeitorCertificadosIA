"""Testes da leitura por OCR (PDF escaneado) e da porta de entrada `ler_pdf`.

O OCR pode errar, então aqui não exigimos 100%: medimos o acerto contra o gabarito e exigimos
um mínimo. A comparação ignora os espaços ("41 %" e "41%" contam como iguais), porque onde o
OCR corta as palavras não muda o que está escrito.
"""

import json

import pytest

from leitor_certificados.ficticio.gerar import gerar_um
from leitor_certificados.leitura import Palavra
from leitor_certificados.leitura.ler import ler_pdf
from leitor_certificados.leitura.ocr import _limpar, _separar_rotulo

ACERTO_MINIMO = 0.90  # fração dos campos do gabarito lidos sem nenhum erro


def _sem_espacos(texto: str) -> str:
    return "".join(texto.split())


@pytest.fixture(scope="module")
def lote(tmp_path_factory):
    """Dois certificados bastam: o OCR leva alguns segundos por página."""
    pasta = tmp_path_factory.mktemp("ocr")
    gabaritos = [gerar_um(pasta, n) for n in (1, 2)]
    return pasta, [json.loads(g.read_text(encoding="utf-8")) for g in gabaritos]


def test_ler_pdf_escolhe_o_caminho_sozinho(lote):
    pasta, gabaritos = lote
    (digital,) = ler_pdf(pasta / gabaritos[0]["digital"]["arquivo"])
    (escaneado,) = ler_pdf(pasta / gabaritos[0]["escaneado"]["arquivo"])
    assert digital.origem == "digital"
    assert escaneado.origem == "ocr"


def test_ocr_le_o_escaneado_com_acerto_minimo(lote):
    pasta, gabaritos = lote
    certos = total = 0
    for gabarito in gabaritos:
        (pagina,) = ler_pdf(pasta / gabarito["escaneado"]["arquivo"])
        for palavra in pagina.palavras:
            assert 0 < palavra.confianca <= 1
            esq, topo, dir_, base = palavra.caixa
            assert 0 <= esq < dir_ <= 1 and 0 <= topo < base <= 1
        for campo in gabarito["escaneado"]["campos"]:
            total += 1
            lido = pagina.texto_na_caixa(campo["caixa"], folga=0.004)
            certos += _sem_espacos(lido) == _sem_espacos(campo["texto"])
    assert certos / total >= ACERTO_MINIMO, f"{certos} de {total}"


def test_limpar_acerta_o_simbolo_de_grau():
    assert _limpar(" 20,4 ℃ ") == "20,4 °C"
    assert _limpar("°℃") == "°C"
    assert _limpar("RC-9844") == "RC-9844"


def test_separar_rotulo_grudado_na_resposta():
    grudada = Palavra("CERTIFICADO:QV050294", (0.60, 0.10, 0.80, 0.12), 0.9)
    rotulo, resposta = _separar_rotulo(grudada)
    assert (rotulo.texto, resposta.texto) == ("CERTIFICADO:", "QV050294")
    assert rotulo.caixa[2] == resposta.caixa[0] == pytest.approx(0.72)
    # Hora, rótulo sozinho e palavra comum ficam como estão
    for texto in ("10:30", "CERTIFICADO:", "Metrovix"):
        palavra = Palavra(texto, (0.1, 0.1, 0.2, 0.12))
        assert _separar_rotulo(palavra) == [palavra]


def test_folha_de_cabeca_para_baixo_e_virada_sozinha(lote, tmp_path):
    """O scanner às vezes puxa a folha invertida: o OCR tenta 180° e fica com a melhor leitura."""
    import pypdfium2 as pdfium

    pasta, gabaritos = lote
    gabarito = gabaritos[0]
    original = pdfium.PdfDocument(str(pasta / gabarito["escaneado"]["arquivo"]))
    imagem = original[0].render(scale=200 / 72).to_pil().rotate(180)
    original.close()
    invertido = tmp_path / "invertido.pdf"
    imagem.save(invertido, "PDF", resolution=200)

    (pagina,) = ler_pdf(invertido)
    assert pagina.rotacao == 180
    certos = total = 0
    for campo in gabarito["escaneado"]["campos"]:
        total += 1
        lido = pagina.texto_na_caixa(campo["caixa"], folga=0.004)
        certos += _sem_espacos(lido) == _sem_espacos(campo["texto"])
    assert certos / total >= 0.85, f"{certos} de {total}"
