"""Assinatura digital do PDF aprovado: intacto depois de assinar; quebra se alguém mexer."""

from pathlib import Path

from reportlab.pdfgen import canvas

from leitor_certificados.assinatura import assinar_pdf, conferir_assinatura, criar_certificado


def _pdf(caminho: Path) -> Path:
    folha = canvas.Canvas(str(caminho))
    folha.drawString(100, 750, "Certificado ficticio")
    folha.save()
    return caminho


def test_assinado_fica_intacto(tmp_path):
    pdf = assinar_pdf(_pdf(tmp_path / "c.pdf"), tmp_path / "cert.pfx", "Aprovado")
    estado = conferir_assinatura(pdf)
    assert estado["assinado"] and estado["intacto"] and estado["documento_inteiro"]
    assert not estado["confiavel"]  # certificado próprio: o Adobe mostra "desconhecida"


def test_mexer_depois_quebra_a_assinatura(tmp_path):
    pdf = assinar_pdf(_pdf(tmp_path / "c.pdf"), tmp_path / "cert.pfx", "Aprovado")
    conteudo = pdf.read_bytes()  # o texto vem comprimido: muda um byte do cabeçalho da página
    assert b"/MediaBox" in conteudo
    pdf.write_bytes(conteudo.replace(b"/MediaBox", b"/MediaBox ", 1))
    assert not conferir_assinatura(pdf)["intacto"]


def test_sem_assinatura(tmp_path):
    assert conferir_assinatura(_pdf(tmp_path / "c.pdf")) == {"assinado": False,
                                                             "intacto": False}


def test_certificado_criado_uma_vez_so(tmp_path):
    arquivo = criar_certificado(tmp_path / "cert.pfx")
    antes = arquivo.read_bytes()
    criar_certificado(arquivo)
    assert arquivo.read_bytes() == antes  # nunca troca a chave de todos
