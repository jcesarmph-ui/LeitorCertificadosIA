"""Planos de calibração INVENTADOS, para testar a etapa 4 sem nenhum dado da empresa.

Cria um banco SQLite com as mesmas tabelas e colunas que o conferidor lê do banco do DQ05
(`instrumentos`, `planos`, `pontos_plano`) e, para cada certificado fictício, um plano com os
mesmos pontos nominais e uma tolerância sorteada — ora folgada, ora apertada — para que alguns
certificados passem e outros sejam reprovados. Devolve também a **resposta certa** (calculada
direto do gabarito) para medir o conferidor.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

from ..conferencia.avaliacao import Resultado, avaliar_ponto, resultado_geral

# tolerância = fator × (maior "erro + U" do certificado). Fator < 1 reprova; > 1 aprova.
# (nunca perto de 1, para o arredondamento não decidir o resultado)
_FATORES = (0.5, 0.7, 0.85, 1.25, 1.5, 2.0, 3.0)

_ESQUEMA = """
CREATE TABLE planos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, excluido_em TEXT);
CREATE TABLE instrumentos (id INTEGER PRIMARY KEY, codigo TEXT NOT NULL, plano_id INTEGER,
                           faixa TEXT, excluido_em TEXT);
CREATE TABLE pontos_plano (
    id INTEGER PRIMARY KEY, plano_id INTEGER NOT NULL, ordem INTEGER, tipo TEXT NOT NULL,
    valor_nominal REAL, tolerancia_inferior REAL, tolerancia_superior REAL, incerteza REAL,
    incerteza_nao_aplica INTEGER DEFAULT 0, excluido_em TEXT);
"""


def criar_banco_de_planos(caminho: Path, certificados: list[dict],
                          semente: int = 2026) -> dict[str, Resultado]:
    """Grava os planos inventados e devolve {id do certificado: resultado certo}."""
    caminho.unlink(missing_ok=True)
    rng = random.Random(f"planos-{semente}")
    con = sqlite3.connect(caminho)
    con.executescript(_ESQUEMA)
    certo: dict[str, Resultado] = {}
    for n, cert in enumerate(certificados, start=1):
        pontos = cert["pontos"]
        maior = max(abs(p["erro"]) + p["incerteza"] for p in pontos)
        tolerancia = float(f"{rng.choice(_FATORES) * max(maior, 1e-6):.3g}")
        # Certificado com critério de aceitação (ADR 0009): metade das vezes o plano usa o mesmo
        # valor (sem aviso); na outra metade, a tolerância sorteada (aviso amarelo).
        criterio = pontos[0].get("criterio") if pontos else None
        if criterio is not None and rng.random() < 0.5:
            tolerancia = criterio
        con.execute("INSERT INTO planos (id, nome) VALUES (?, ?)", (n, f"Plano {cert['tipo']}"))
        faixa = f"{cert['faixa_min']:g}-{cert['faixa_max']:g}"  # como o cadastro real ("0-500")
        con.execute("INSERT INTO instrumentos (id, codigo, plano_id, faixa) VALUES (?, ?, ?, ?)",
                    (n, cert["codigo"], n, faixa))
        resultados = []
        for ordem, p in enumerate(pontos):
            con.execute(
                "INSERT INTO pontos_plano (plano_id, ordem, tipo, valor_nominal, "
                "tolerancia_inferior, tolerancia_superior, incerteza) "
                "VALUES (?, ?, 'NUMERICO', ?, ?, ?, ?)",
                (n, ordem, p["nominal"], -tolerancia, tolerancia, p["incerteza"]))
            resultados.append(avaliar_ponto(
                p["erro"], incerteza=p["incerteza"], tolerancia_inferior=-tolerancia,
                tolerancia_superior=tolerancia).resultado)
        certo[cert["id"]] = resultado_geral(resultados)
    con.commit()
    con.close()
    return certo
