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
    nominal: float | None  # None quando o ponto é um intervalo (durômetro)
    tolerancia_inferior: float | None
    tolerancia_superior: float | None
    incerteza: float | None  # a do plano é só sugestão: a que vale é a do certificado
    sem_incerteza: bool = False  # "U não se aplica"
    # durômetro: o ponto é um intervalo numa escala ("67 a 80 HR15T"); o padrão do
    # certificado tem de estar dentro dele (ensinado pelo usuário, 2026-11-17)
    minimo: float | None = None
    maximo: float | None = None
    escala: str | None = None

    def aceita(self, nominal: float, escala: str | None = None) -> bool:
        """O nominal do certificado é este ponto? Igual ao nominal ou, no intervalo, dentro
        dele e na mesma escala (sem escala lida, só o intervalo)."""
        if self.nominal is not None:
            return abs(self.nominal - nominal) <= 1e-6 * max(1.0, abs(nominal))
        if self.minimo is None or self.maximo is None:
            return False
        if escala and self.escala and escala != self.escala:
            return False
        return self.minimo - 1e-9 <= nominal <= self.maximo + 1e-9


_INTERVALO = re.compile(r"(\d+(?:[.,]\d+)?)\s*a\s*(\d+(?:[.,]\d+)?)\s*(HR\s?\w+)",
                        re.IGNORECASE)


def intervalo_da_descricao(descricao: str | None) -> tuple[float, float, str] | None:
    """"1º ponto 67 a 80 HR15T" → (67, 80, "HR15T"); None se não for desse jeito."""
    from .extracao import escala_de_dureza

    achou = _INTERVALO.search(descricao or "")
    if not achou:
        return None
    escala = escala_de_dureza(achou.group(3))
    if escala is None:
        return None
    return (float(achou.group(1).replace(",", ".")), float(achou.group(2).replace(",", ".")),
            escala)


@dataclass
class Plano:
    codigo: str
    nome: str
    pontos: list[PontoDoPlano] = field(default_factory=list)
    faixa: str | None = None  # texto livre do cadastro do instrumento ("0-500", "0 a 25 mm")
    # o que o cadastro diz do instrumento (para o comparador do painel Instrumento)
    cadastro: dict[str, str | None] = field(default_factory=dict)


def normalizar_codigo(codigo: str) -> str:
    """"paq - 018", "PAQ018" e "PAQ-018" viram a mesma chave."""
    sem_acento = unicodedata.normalize("NFKD", codigo).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", sem_acento.upper())


def _sem_zeros(chave: str) -> str:
    """"GON002" → "GON2": tira os zeros à esquerda de cada número."""
    return re.sub(r"(?<!\d)0+(?=\d)", "", chave)


class PlanosDQ05:
    """Lê instrumentos e planos de uma cópia do banco do DQ05, sem nunca alterar nada."""

    def __init__(self, caminho: Path | str):
        caminho = Path(caminho).resolve()
        self._con = sqlite3.connect(f"file:{caminho.as_posix()}?mode=ro", uri=True)
        self._con.row_factory = sqlite3.Row
        self._plano_por_codigo: dict[str, int] = {}
        self._faixa_por_codigo: dict[str, str | None] = {}
        self._cadastro_por_codigo: dict[str, dict[str, str | None]] = {}
        existentes = {c["name"] for c in self._con.execute("PRAGMA table_info(instrumentos)")}
        # colunas que bancos mais antigos (ou o banco fictício dos testes) podem não ter
        extras = ", ".join(c if c in existentes else f"NULL AS {c}"
                           for c in ("faixa", "tipo", "fabricante", "resolucao"))
        for linha in self._con.execute(
            f"SELECT codigo, plano_id, {extras} FROM instrumentos "
            "WHERE excluido_em IS NULL AND plano_id IS NOT NULL"
        ):
            chave = normalizar_codigo(linha["codigo"])
            self._plano_por_codigo[chave] = linha["plano_id"]
            self._faixa_por_codigo[chave] = linha["faixa"]
            self._cadastro_por_codigo[chave] = {
                "codigo": linha["codigo"], "tipo": linha["tipo"],
                "fabricante": linha["fabricante"], "faixa": linha["faixa"],
                "resolucao": None if linha["resolucao"] is None else str(linha["resolucao"])}

    def fechar(self) -> None:
        self._con.close()

    def _chave(self, codigo: str) -> str:
        """A chave do cadastro para o código. "GON-02" acha "GON-002" (zeros à esquerda do número
        não contam; decisão do usuário, 2026-11-16) — só se houver um único instrumento assim."""
        chave = normalizar_codigo(codigo)
        if chave in self._plano_por_codigo:
            return chave
        parecidos = [c for c in self._plano_por_codigo if _sem_zeros(c) == _sem_zeros(chave)]
        return parecidos[0] if len(parecidos) == 1 else chave

    def candidatos(self, codigo: str) -> list[str]:
        """Os instrumentos que podem ser este código quando há dúvida (zeros à esquerda): mais de
        um quando o cadastro tem, por exemplo, "PAQ-007" e "PAQ-0007" para um "PAQ-7"."""
        chave = normalizar_codigo(codigo)
        if chave in self._plano_por_codigo:
            return [chave]
        return [c for c in self._plano_por_codigo if _sem_zeros(c) == _sem_zeros(chave)]

    def conhece(self, codigo: str) -> bool:
        return self._chave(codigo) in self._plano_por_codigo

    def plano_do_instrumento(self, codigo: str) -> Plano | None:
        """O plano do instrumento (só pontos numéricos com tolerância), ou None se o código não
        existe no cadastro ou o instrumento não tem plano."""
        plano_id = self._plano_por_codigo.get(self._chave(codigo))
        if plano_id is None:
            return None
        cabecalho = self._con.execute(
            "SELECT nome FROM planos WHERE id = ? AND excluido_em IS NULL", (plano_id,)
        ).fetchone()
        if cabecalho is None:
            return None
        pontos = []
        colunas = {c[1] for c in self._con.execute("PRAGMA table_info(pontos_plano)")}
        descricao = "descricao" if "descricao" in colunas else "NULL AS descricao"
        for linha in self._con.execute(
                "SELECT valor_nominal, tolerancia_inferior, tolerancia_superior, incerteza, "
                f"incerteza_nao_aplica, {descricao} FROM pontos_plano "
                "WHERE plano_id = ? AND tipo = 'NUMERICO' AND excluido_em IS NULL "
                "ORDER BY ordem",
                (plano_id,)):
            intervalo = (intervalo_da_descricao(linha["descricao"])
                         if linha["valor_nominal"] is None else None)
            if linha["valor_nominal"] is None and intervalo is None:
                continue  # sem número nem intervalo: não há o que conferir
            minimo, maximo, escala = intervalo or (None, None, None)
            pontos.append(PontoDoPlano(
                nominal=linha["valor_nominal"],
                tolerancia_inferior=linha["tolerancia_inferior"],
                tolerancia_superior=linha["tolerancia_superior"],
                incerteza=linha["incerteza"],
                sem_incerteza=bool(linha["incerteza_nao_aplica"]),
                minimo=minimo, maximo=maximo, escala=escala,
            ))
        return Plano(codigo=codigo, nome=cabecalho["nome"], pontos=pontos,
                     faixa=self._faixa_por_codigo.get(self._chave(codigo)),
                     cadastro=dict(self._cadastro_por_codigo.get(self._chave(codigo), {})))
