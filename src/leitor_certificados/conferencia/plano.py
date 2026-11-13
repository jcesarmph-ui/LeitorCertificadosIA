"""O plano de calibração de um instrumento, lido do banco do programa DQ05.

O banco é aberto **só para leitura** (`mode=ro`): este projeto nunca escreve nele. Trabalhe sempre
numa **cópia** do banco (feita com a API de backup do SQLite) guardada em `dados/`, fora do Git.

Só os pontos **numéricos** têm tolerância que o certificado consegue conferir; os demais tipos do
plano (qualitativos, critérios, classe) ficam de fora desta etapa.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PontoDoPlano:
    nominal: float
    tolerancia_inferior: float | None
    tolerancia_superior: float | None
    incerteza: float | None  # a do plano é só sugestão: a que vale é a do certificado
    sem_incerteza: bool = False  # "U não se aplica"


@dataclass
class Plano:
    codigo: str
    nome: str
    pontos: list[PontoDoPlano] = field(default_factory=list)
    faixa: str | None = None  # texto livre do cadastro do instrumento ("0-500", "0 a 25 mm")


def normalizar_codigo(codigo: str) -> str:
    """"paq - 018", "PAQ018" e "PAQ-018" viram a mesma chave."""
    sem_acento = unicodedata.normalize("NFKD", codigo).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", sem_acento.upper())


class PlanosDQ05:
    """Lê instrumentos e planos de uma cópia do banco do DQ05, sem nunca alterar nada."""

    def __init__(self, caminho: Path | str):
        caminho = Path(caminho).resolve()
        self._con = sqlite3.connect(f"file:{caminho.as_posix()}?mode=ro", uri=True)
        self._con.row_factory = sqlite3.Row
        self._plano_por_codigo: dict[str, int] = {}
        self._faixa_por_codigo: dict[str, str | None] = {}
        tem_faixa = any(c["name"] == "faixa"
                        for c in self._con.execute("PRAGMA table_info(instrumentos)"))
        coluna_faixa = "faixa" if tem_faixa else "NULL AS faixa"
        for linha in self._con.execute(
            f"SELECT codigo, plano_id, {coluna_faixa} FROM instrumentos "
            "WHERE excluido_em IS NULL AND plano_id IS NOT NULL"
        ):
            chave = normalizar_codigo(linha["codigo"])
            self._plano_por_codigo[chave] = linha["plano_id"]
            self._faixa_por_codigo[chave] = linha["faixa"]

    def fechar(self) -> None:
        self._con.close()

    def conhece(self, codigo: str) -> bool:
        return normalizar_codigo(codigo) in self._plano_por_codigo

    def plano_do_instrumento(self, codigo: str) -> Plano | None:
        """O plano do instrumento (só pontos numéricos com tolerância), ou None se o código não
        existe no cadastro ou o instrumento não tem plano."""
        plano_id = self._plano_por_codigo.get(normalizar_codigo(codigo))
        if plano_id is None:
            return None
        cabecalho = self._con.execute(
            "SELECT nome FROM planos WHERE id = ? AND excluido_em IS NULL", (plano_id,)
        ).fetchone()
        if cabecalho is None:
            return None
        pontos = [
            PontoDoPlano(
                nominal=linha["valor_nominal"],
                tolerancia_inferior=linha["tolerancia_inferior"],
                tolerancia_superior=linha["tolerancia_superior"],
                incerteza=linha["incerteza"],
                sem_incerteza=bool(linha["incerteza_nao_aplica"]),
            )
            for linha in self._con.execute(
                "SELECT valor_nominal, tolerancia_inferior, tolerancia_superior, incerteza, "
                "incerteza_nao_aplica FROM pontos_plano "
                "WHERE plano_id = ? AND tipo = 'NUMERICO' AND excluido_em IS NULL "
                "AND valor_nominal IS NOT NULL ORDER BY ordem",
                (plano_id,),
            )
        ]
        return Plano(codigo=codigo, nome=cabecalho["nome"], pontos=pontos,
                     faixa=self._faixa_por_codigo.get(normalizar_codigo(codigo)))
