"""O banco dos planos numa pasta da rede abre só para leitura."""

import sqlite3
from pathlib import PureWindowsPath

from leitor_certificados.conferencia.plano import uri_somente_leitura


def test_caminho_da_rede_ganha_quatro_barras():
    caminho = PureWindowsPath(r"\\Servidor\pasta comum\dados\calibracao.db")
    assert uri_somente_leitura(caminho) == (
        "file:////Servidor/pasta comum/dados/calibracao.db?mode=ro")


def test_caminho_local_e_caracteres_especiais(tmp_path):
    pasta = tmp_path / "Calibração #1"
    pasta.mkdir()
    banco = pasta / "calibracao.db"
    sqlite3.connect(banco).execute("create table t (x)").connection.close()
    uri = uri_somente_leitura(banco)
    assert "%23" in uri and uri.endswith("?mode=ro")
    conexao = sqlite3.connect(uri, uri=True)
    assert conexao.execute("select count(*) from t").fetchone() == (0,)
    conexao.close()
