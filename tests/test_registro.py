"""Testes do registro das análises (etapa 10): gravar, Lixeira, restaurar, apagar de vez e a
planilha. Só dados inventados, numa pasta temporária."""

from openpyxl import load_workbook

from leitor_certificados.registro import RegistroAnalises

FOLHA = {"origem": "digital", "rotacao": 0,
         "palavras": [{"i": 0, "texto": "XYZ-01", "caixa": [0, 0, 1, 1], "confianca": 1.0,
                       "rotulo": "outro", "certeza": 0.4, "certo": "codigo"}]}


def _registrar(registro: RegistroAnalises, chave: str = "cert_a", marcacao=FOLHA) -> int:
    return registro.registrar(
        usuario="fulano", pc="PC-TESTE", certificado=f"{chave}.pdf", chave=chave,
        sha256="ab" * 32, codigo="XYZ-01", plano="Plano inventado", parecer="APROVADO",
        motivos={"erros": [], "avisos": ["Faixa diferente"]}, lido={"campos": {}},
        correcoes=1 if marcacao else 0, textos=0, manual={"faixa": "0 a 10 mm"},
        marcacao=marcacao, versao_programa="0.10.0", versao_modelo="teste")


def test_registra_e_lista_o_mais_novo_primeiro(tmp_path):
    registro = RegistroAnalises(tmp_path / "registro" / "registro.db")
    assert registro.listar() == []  # banco ainda nem existe: lista vazia, sem erro
    primeiro = _registrar(registro)
    segundo = _registrar(registro, "cert_b")
    lista = registro.listar()
    assert [r.id for r in lista] == [segundo, primeiro]
    r = registro.obter(primeiro)
    assert r.usuario == "fulano" and r.pc == "PC-TESTE" and r.parecer == "APROVADO"
    assert r.manual == {"faixa": "0 a 10 mm"} and r.marcacao == FOLHA and r.ensina


def test_lixeira_restaurar_e_apagar_de_vez(tmp_path):
    registro = RegistroAnalises(tmp_path / "registro.db")
    numero = _registrar(registro)
    registro.apagar_de_vez(numero)  # ativo: apagar de vez não faz nada (só da Lixeira)
    assert registro.obter(numero) is not None
    registro.mandar_para_lixeira(numero)
    assert registro.listar() == [] and [r.id for r in registro.listar(lixeira=True)] == [numero]
    assert registro.vigentes() == {}  # na Lixeira não ensina
    registro.restaurar(numero)
    assert registro.vigentes() == {"cert_a": FOLHA}
    registro.mandar_para_lixeira(numero)
    registro.apagar_de_vez(numero)
    assert registro.obter(numero) is None


def test_vale_a_folha_do_registro_mais_novo_de_cada_certificado(tmp_path):
    registro = RegistroAnalises(tmp_path / "registro.db")
    _registrar(registro)
    novo = _registrar(registro, marcacao=None)  # a pessoa desfez todas as correções
    assert registro.vigentes() == {"cert_a": None}
    registro.mandar_para_lixeira(novo)  # desfaz o desfazer: volta a folha anterior
    assert registro.vigentes() == {"cert_a": FOLHA}


def test_planilha_tem_aba_do_registro_e_da_lixeira(tmp_path):
    registro = RegistroAnalises(tmp_path / "registro.db")
    _registrar(registro)
    registro.mandar_para_lixeira(_registrar(registro, "cert_b"))
    livro = load_workbook(registro.exportar_planilha(tmp_path / "registro.xlsx"))
    assert livro.sheetnames == ["Registro", "Lixeira"]
    ativo = [linha for linha in livro["Registro"].iter_rows(values_only=True)]
    assert ativo[0][0] == "Nº" and ativo[1][4] == "cert_a.pdf" and ativo[1][10] == "Faixa diferente"
    assert livro["Lixeira"].max_row == 2
