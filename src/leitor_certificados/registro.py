"""Registro das análises: rastreabilidade e transparência (etapa 10, ADR 0012).

Cada vez que a pessoa clica em "Registrar", fica guardado quem, quando, em qual PC, qual
certificado (com a "impressão digital" SHA-256 do arquivo), o que o modelo leu, o que foi
corrigido ou digitado à mão, o parecer, a versão do programa e a do modelo.

As correções só ensinam o modelo depois de registradas (decisão do usuário, 2026-11-17): assim
tudo o que o modelo aprendeu está aqui e pode ser desfeito. Mandar um registro para a Lixeira
tira o aprendizado dele na hora; restaurar devolve; apagar de vez some para sempre.

Guardado num banco SQLite na pasta de dados (fora do Git). Modo journal tradicional (nunca WAL:
não funciona em pasta de rede), `busy_timeout` e transações curtas, como nos outros programas.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ESQUEMA = 2  # 2: aprovação final pelo responsável e PDFs guardados (etapa 11)

# colunas que o esquema 2 acrescenta (o banco antigo ganha as colunas ao abrir; nada se perde)
_COLUNAS_NOVAS = {
    "arquivo_conferido": "TEXT",  # cópia do PDF com os checks da conferência
    "aprovado_por": "TEXT",       # nome do responsável que aprovou de vez
    "aprovado_re": "TEXT",        # RE (matrícula) do responsável
    "aprovado_data": "TEXT",      # data da aprovação, como digitada (dd/mm/aaaa)
    "aprovado_em": "TEXT",        # quando foi clicado (data e hora), usuário e PC: auditoria
    "aprovado_usuario": "TEXT",
    "aprovado_pc": "TEXT",
    "arquivo_aprovado": "TEXT",   # cópia do PDF com os checks e o carimbo
    "decisao": "TEXT",            # APROVADO ou REPROVADO (decisão de quem conferiu)
}

_CRIAR = """
CREATE TABLE IF NOT EXISTS metadados (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS analises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT NOT NULL,          -- 2026-11-17 14:05:31
    usuario TEXT NOT NULL,            -- usuário do Windows
    pc TEXT NOT NULL,                 -- nome do computador
    certificado TEXT NOT NULL,        -- nome do arquivo
    chave TEXT NOT NULL,              -- nome sem extensão: liga às correções do certificado
    sha256 TEXT NOT NULL,             -- impressão digital do PDF (prova de qual arquivo foi)
    codigo TEXT,                      -- código do instrumento usado na conferência
    plano TEXT,
    parecer TEXT,
    motivos TEXT NOT NULL,            -- JSON: {"erros": [...], "avisos": [...]}
    lido TEXT NOT NULL,               -- JSON: campos, pontos e padrões que o modelo leu
    correcoes INTEGER NOT NULL,       -- quantas palavras a pessoa mudou
    textos INTEGER NOT NULL,          -- quantos textos do OCR a pessoa corrigiu
    manual TEXT NOT NULL,             -- JSON: valores digitados à mão
    marcacao TEXT,                    -- JSON: a folha corrigida (o que ensina o modelo)
    versao_programa TEXT NOT NULL,
    versao_modelo TEXT NOT NULL,
    na_lixeira_em TEXT                -- vazio = ativo
);
"""


@dataclass
class Registro:
    id: int
    data_hora: str
    usuario: str
    pc: str
    certificado: str
    chave: str
    sha256: str
    codigo: str | None
    plano: str | None
    parecer: str | None
    motivos: dict
    lido: dict
    correcoes: int
    textos: int
    manual: dict
    marcacao: dict | None
    versao_programa: str
    versao_modelo: str
    na_lixeira_em: str | None
    arquivo_conferido: str | None = None
    aprovado_por: str | None = None
    aprovado_re: str | None = None
    aprovado_data: str | None = None
    aprovado_em: str | None = None
    aprovado_usuario: str | None = None
    aprovado_pc: str | None = None
    arquivo_aprovado: str | None = None
    decisao: str | None = None

    @property
    def decidido(self) -> bool:
        """O responsável já decidiu (aprovou ou rejeitou)."""
        return bool(self.aprovado_por)

    @property
    def aprovado(self) -> bool:
        """O responsável aprovou de vez (vale mais que o parecer da IA)."""
        return self.decidido and (self.decisao or "APROVADO") == "APROVADO"

    @property
    def parecer_final(self) -> str | None:
        """O que vale: a decisão do responsável ou, sem ela, o parecer da IA."""
        return (self.decisao or "APROVADO") if self.decidido else self.parecer

    @property
    def ensina(self) -> bool:
        """Este registro ensina o modelo? (tem correções e não está na Lixeira)"""
        return self.na_lixeira_em is None and bool(self.correcoes or self.textos)


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RegistroAnalises:
    """O banco do registro. Abre e fecha a conexão a cada operação: pode ser usado de qualquer
    thread e nunca deixa o arquivo preso."""

    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)

    def _abrir(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute("PRAGMA busy_timeout=10000")
        con.executescript(_CRIAR)
        existentes = {linha[1] for linha in con.execute("PRAGMA table_info(analises)")}
        with con:
            for coluna, tipo in _COLUNAS_NOVAS.items():
                if coluna not in existentes:
                    con.execute(f"ALTER TABLE analises ADD COLUMN {coluna} {tipo}")
            con.execute("INSERT OR REPLACE INTO metadados VALUES ('esquema', ?)", (str(ESQUEMA),))
        return con

    def _executar(self, sql: str, parametros: tuple = ()) -> list[sqlite3.Row]:
        con = self._abrir()
        try:
            with con:
                linhas = con.execute(sql, parametros).fetchall()
            return linhas
        finally:
            con.close()

    @staticmethod
    def _registro(linha: sqlite3.Row) -> Registro:
        d = dict(linha)
        for campo in ("motivos", "lido", "manual"):
            d[campo] = json.loads(d[campo])
        d["marcacao"] = json.loads(d["marcacao"]) if d["marcacao"] else None
        return Registro(**d)

    # ------------------------------------------------------------------ gravar
    def registrar(self, *, usuario: str, pc: str, certificado: str, chave: str, sha256: str,
                  codigo: str | None, plano: str | None, parecer: str | None, motivos: dict,
                  lido: dict, correcoes: int, textos: int, manual: dict,
                  marcacao: dict | None, versao_programa: str, versao_modelo: str) -> int:
        con = self._abrir()
        try:
            with con:
                cursor = con.execute(
                    "INSERT INTO analises (data_hora, usuario, pc, certificado, chave, sha256, "
                    "codigo, plano, parecer, motivos, lido, correcoes, textos, manual, marcacao, "
                    "versao_programa, versao_modelo) VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (_agora(), usuario, pc, certificado, chave, sha256, codigo, plano, parecer,
                     json.dumps(motivos, ensure_ascii=False),
                     json.dumps(lido, ensure_ascii=False), correcoes, textos,
                     json.dumps(manual, ensure_ascii=False),
                     json.dumps(marcacao, ensure_ascii=False) if marcacao else None,
                     versao_programa, versao_modelo))
                return int(cursor.lastrowid)
        finally:
            con.close()

    def guardar_conferido(self, id_: int, arquivo: str) -> None:
        self._executar("UPDATE analises SET arquivo_conferido = ? WHERE id = ?", (arquivo, id_))

    def aprovar(self, id_: int, *, nome: str, re: str, data: str, usuario: str, pc: str,
                arquivo: str, decisao: str = "APROVADO") -> None:
        """Aprovação final pelo responsável: o registro passa a constar APROVADO, mesmo que a
        IA tenha dado pendente ou reprovado. O parecer da IA continua guardado."""
        self._executar(
            "UPDATE analises SET aprovado_por = ?, aprovado_re = ?, aprovado_data = ?, "
            "aprovado_em = ?, aprovado_usuario = ?, aprovado_pc = ?, arquivo_aprovado = ?, "
            "decisao = ? WHERE id = ?",
            (nome, re, data, _agora(), usuario, pc, arquivo, decisao, id_))

    def apagar_aprovacao(self, id_: int) -> None:
        """Aprovação feita sem querer: some (decisão do usuário, 2026-11-17)."""
        self._executar(
            "UPDATE analises SET aprovado_por = NULL, aprovado_re = NULL, aprovado_data = NULL, "
            "aprovado_em = NULL, aprovado_usuario = NULL, aprovado_pc = NULL, "
            "arquivo_aprovado = NULL, decisao = NULL WHERE id = ?", (id_,))

    def mandar_para_lixeira(self, id_: int) -> None:
        self._executar("UPDATE analises SET na_lixeira_em = ? WHERE id = ?", (_agora(), id_))

    def restaurar(self, id_: int) -> None:
        self._executar("UPDATE analises SET na_lixeira_em = NULL WHERE id = ?", (id_,))

    def apagar_de_vez(self, id_: int) -> None:
        """Só apaga o que já está na Lixeira (nunca um registro ativo por engano)."""
        self._executar("DELETE FROM analises WHERE id = ? AND na_lixeira_em IS NOT NULL",
                       (id_,))

    # ------------------------------------------------------------------ ler
    def listar(self, lixeira: bool = False) -> list[Registro]:
        """Os registros ativos (ou os da Lixeira), o mais novo primeiro."""
        filtro = "IS NOT NULL" if lixeira else "IS NULL"
        if not self.caminho.exists():
            return []
        return [self._registro(linha) for linha in self._executar(
            f"SELECT * FROM analises WHERE na_lixeira_em {filtro} ORDER BY id DESC")]

    def obter(self, id_: int) -> Registro | None:
        linhas = self._executar("SELECT * FROM analises WHERE id = ?", (id_,))
        return self._registro(linhas[0]) if linhas else None

    def vigentes(self) -> dict[str, dict | None]:
        """{chave: folha corrigida} pelo registro ativo MAIS NOVO de cada certificado — o que
        ensina o modelo. None quando o registro mais novo não tem correção (a pessoa desfez
        todas): aí aquele certificado não ensina nada."""
        vigentes: dict[str, dict | None] = {}
        for r in self.listar():  # do mais novo para o mais antigo: fica o mais novo
            vigentes.setdefault(r.chave, r.marcacao)
        return vigentes

    # ------------------------------------------------------------------ planilha
    def exportar_planilha(self, destino: Path | str) -> Path:
        """Gera uma planilha .xlsx (uma aba para os ativos e outra para a Lixeira). É só uma
        cópia para ler e filtrar no Excel: o registro de verdade continua no banco."""
        from openpyxl import Workbook
        from openpyxl.styles import Font

        cabecalho = ["Nº", "Data e hora", "Usuário", "PC", "Certificado", "SHA-256",
                     "Código", "Plano", "Parecer", "Problemas", "Avisos",
                     "Palavras corrigidas", "Textos corrigidos", "Digitado à mão",
                     "Versão do programa", "Versão do modelo", "Na Lixeira desde",
                     "Parecer final", "Aprovado por", "RE", "Data da aprovação",
                     "Aprovação registrada em"]
        livro = Workbook()
        abas = [(livro.active, "Registro", False), (None, "Lixeira", True)]
        for aba, nome, lixeira in abas:
            aba = aba or livro.create_sheet()
            aba.title = nome
            aba.append(cabecalho)
            for celula in aba[1]:
                celula.font = Font(bold=True)
            for r in self.listar(lixeira):
                aba.append([
                    r.id, r.data_hora, r.usuario, r.pc, r.certificado, r.sha256,
                    r.codigo or "", r.plano or "", r.parecer or "",
                    "\n".join(r.motivos.get("erros", [])),
                    "\n".join(r.motivos.get("avisos", [])),
                    r.correcoes, r.textos,
                    "; ".join(f"{k}: {v}" for k, v in r.manual.items()),
                    r.versao_programa, r.versao_modelo, r.na_lixeira_em or "",
                    r.parecer_final or "", r.aprovado_por or "", r.aprovado_re or "",
                    r.aprovado_data or "",
                    f"{r.aprovado_em} ({r.aprovado_usuario} - {r.aprovado_pc})"
                    if r.aprovado else ""])
            aba.freeze_panes = "A2"
            aba.auto_filter.ref = aba.dimensions
            for coluna in aba.columns:
                largura = max(len(str(c.value or "")) for c in coluna)
                aba.column_dimensions[coluna[0].column_letter].width = min(largura + 2, 60)
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        livro.save(destino)
        return destino
