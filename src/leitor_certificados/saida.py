"""A saída do leitor para o sistema de calibração (etapa 13, ADR 0012).

O leitor vira uma peça do sistema de calibração: a pessoa lê o certificado, confere, decide
(Aprovar/Rejeitar) e o sistema **preenche a calibração sozinho** com o que sai daqui — os pontos
vão direto para a linha certa do plano (pelo `id_ponto_plano`), sem digitar um por um, e o PDF
carimbado já vai junto (o "Subir PDF" do sistema fica travado).

Tudo em tipos simples (texto, número, lista, dicionário), para virar JSON sem esforço e o sistema
não depender das classes internas do leitor. `VERSAO` muda se o formato mudar.
"""

from __future__ import annotations

from pathlib import Path

from .conferencia.padroes import data_br
from .interface.servico import Analise, ignoradas, pendencias
from .registro import Registro

VERSAO = 1


def _numero(x: float | None) -> float | None:
    return None if x is None else round(float(x), 6)


def saida_para_sistema(analise: Analise, registro: Registro | None = None,
                       pdf_final: Path | str | None = None) -> dict:
    """O resultado da análise (e da decisão, se já registrada) para o sistema de calibração."""
    c = analise.conferencia
    pd = c.padroes if c else None
    fora = set(ignoradas(analise))
    pontos, fora_do_plano = [], []
    for p in (c.pontos if c else []):
        item = {
            "nominal_lido": _numero(p.lido.nominal),
            "encontrado": _numero(p.lido.encontrado),
            "erro": _numero(p.erro),
            "incerteza": _numero(p.lido.incerteza),
            "escala": p.lido.escala,
            "graus_minutos": p.lido.graus_minutos,
            "resultado": p.avaliacao.resultado.value,
            "avisos": list(p.avisos),
        }
        if p.plano is None:
            fora_do_plano.append(item)
            continue
        pontos.append({
            "id_ponto_plano": p.plano.id,
            "nominal_plano": _numero(p.plano.nominal),
            "minimo_plano": _numero(p.plano.minimo),
            "maximo_plano": _numero(p.plano.maximo),
            "tolerancia_inferior": _numero(p.plano.tolerancia_inferior),
            "tolerancia_superior": _numero(p.plano.tolerancia_superior),
            **item,
        })
    decidido = registro is not None and registro.decidido
    return {
        "versao_saida": VERSAO,
        "certificado": analise.caminho.name,
        "pdf_final": str(pdf_final) if pdf_final else None,
        "codigo": c.codigo if c else analise.manual.get("codigo"),
        "plano": c.plano_nome if c else None,
        "data_calibracao": (pd.data_calibracao.isoformat()
                            if pd and pd.data_calibracao else None),
        "data_calibracao_texto": pd.data_calibracao_texto if pd else None,
        "parecer_leitor": c.resultado.value if c else None,
        "decisao": registro.parecer_final if decidido else None,
        "decidido_por": registro.aprovado_por if decidido else None,
        "re": registro.aprovado_re if decidido else None,
        "data_decisao": registro.aprovado_data if decidido else None,
        "numero_registro": registro.id if registro else None,
        "pontos": pontos,
        "pontos_fora_do_plano": fora_do_plano,
        "padroes": [{"validade": x.validade_texto,
                     "valida_ate": data_br(x.validade.ate) if x.validade else None,
                     "situacao": x.situacao.value}
                    for x in (pd.padroes if pd else [])],
        "padroes_calibrados_marcado": analise.manual.get("padroes_calibrados") == "sim",
        "problemas": list(c.erros) if c else [],
        "pendencias": [{"texto": t, "ignorada": t in fora} for t in pendencias(analise)],
    }
