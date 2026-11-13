"""Laboratórios INVENTADOS, cada um com o seu jeito de montar o certificado.

Por que vários: na vida real cada laboratório usa um modelo de folha diferente — outra ordem das
colunas, outros nomes ("Valor indicado", "Leitura", "VI"…), outro formato de data e de número.
Se o modelo de ML só visse um modelo de folha, ele "decoraria" as posições e erraria no primeiro
certificado diferente. Com vários, ele precisa aprender o que cada informação **é**.

Nomes, endereços e numerações são inventados; qualquer semelhança com um laboratório real é
coincidência. Todo certificado gerado diz no rodapé que é fictício.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

# Colunas possíveis da tabela de pontos
INDICE, NOMINAL, ENCONTRADO, ERRO, INCERTEZA, K = (
    "indice", "nominal", "encontrado", "erro", "incerteza", "k",
)
# Colunas que alguns laboratórios acrescentam (ADR 0009):
# - PARAMETRO: o que foi medido naquela linha ("Face externa"…); é texto, não é campo;
# - ERRO_MAXIMO: erro somado à incerteza (|erro| + U), já calculado pelo laboratório;
# - CRITERIO: critério de aceitação ± adotado pelo cliente (o laboratório compara com ele).
PARAMETRO, ERRO_MAXIMO, CRITERIO = "parametro", "erro_maximo", "criterio"


@dataclass(frozen=True)
class Laboratorio:
    chave: str
    nome: str
    endereco: str
    fonte: str  # "Helvetica", "Times" ou "Courier" (fontes que todo leitor de PDF tem)
    cabecalho: str  # "centro", "faixa" ou "esquerda"
    info: str  # "lista" (uma informação por linha) ou "grade" (duas colunas dentro de um quadro)
    titulo: str
    rotulos: dict[str, str]  # nome que este laboratório dá a cada informação
    ordem_info: tuple[str, ...]  # em que ordem as informações aparecem
    colunas: tuple[str, ...]  # colunas da tabela de pontos, na ordem deste laboratório
    titulos_colunas: dict[str, str]
    formato_data: str  # "dd/mm/aaaa", "extenso", "dd.mm.aaaa", "iso", "dd/mmm/aaaa"
    decimal: str  # "," ou "."
    palavra_faixa: str  # "0 a 150", "0 - 150", "0 to 150"
    sinal_mais: bool  # erro positivo escrito com "+"?
    nota: str  # observação sobre a incerteza (quando não há coluna k, diz o k aqui)
    numero: Callable[[random.Random, date], str]  # como este laboratório numera os certificados
    # unidade numa linha própria embaixo dos títulos (e não "Erro (mm)" no título)
    unidade_em_linha: bool = False
    # frase acima da tabela com o critério de aceitação; "{criterio}" vira "± 0,05 mm"
    frase_criterio: str | None = None


def formatar_data(d: date, formato: str) -> str:
    if formato == "dd/mm/aaaa":
        return d.strftime("%d/%m/%Y")
    if formato == "dd.mm.aaaa":
        return d.strftime("%d.%m.%Y")
    if formato == "iso":
        return d.isoformat()
    if formato == "extenso":
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    if formato == "dd/mmm/aaaa":
        return f"{d.day:02d}/{MESES[d.month - 1][:3]}/{d.year}"
    raise ValueError(f"formato de data desconhecido: {formato}")


def formatar_numero(valor: float, casas: int, decimal: str, sinal_mais: bool = False) -> str:
    if round(valor, casas) == 0:
        valor = 0.0  # zero sempre sem sinal (nem "+0,00" nem "-0,00")
        sinal_mais = False
    texto = f"{valor:+.{casas}f}" if sinal_mais else f"{valor:.{casas}f}"
    return texto.replace(".", decimal)


_BASICO_PT = {
    "numero": "Certificado nº",
    "cliente": "Cliente",
    "tipo": "Instrumento",
    "codigo": "Identificação",
    "fabricante": "Fabricante",
    "serie": "Nº de série",
    "faixa": "Faixa de medição",
    "resolucao": "Resolução",
    "data_calibracao": "Data da calibração",
    "data_emissao": "Data de emissão",
    "temperatura": "Temperatura ambiente",
    "umidade": "Umidade relativa",
    "tecnico": "Técnico executante",
}

LABORATORIOS: dict[str, Laboratorio] = {
    lab.chave: lab
    for lab in (
        Laboratorio(
            chave="serra_clara",
            nome="Metrologia Serra Clara",
            endereco="Rua das Medidas, 120 - Distrito Industrial - Vale Verde/MG",
            fonte="Helvetica",
            cabecalho="centro",
            info="lista",
            titulo="CERTIFICADO DE CALIBRAÇÃO",
            rotulos=_BASICO_PT,
            ordem_info=(
                "cliente", "tipo", "codigo", "fabricante", "serie", "faixa", "resolucao",
                "data_calibracao", "data_emissao", "temperatura", "umidade",
            ),
            colunas=(NOMINAL, ENCONTRADO, ERRO, INCERTEZA, K),
            titulos_colunas={
                NOMINAL: "Valor nominal", ENCONTRADO: "Valor indicado", ERRO: "Erro",
                INCERTEZA: "Incerteza (U)", K: "k",
            },
            formato_data="dd/mm/aaaa",
            decimal=",",
            palavra_faixa="a",
            sinal_mais=False,
            nota="A incerteza expandida (U) corresponde a uma probabilidade de abrangência de "
            "aproximadamente 95%.",
            numero=lambda rng, d: f"SC-{d.year}-{rng.randint(1, 99999):05d}",
        ),
        Laboratorio(
            chave="pedra_azul",
            nome="Instituto Pedra Azul de Metrologia",
            endereco="Av. Tolerância, 45 - Centro - Pedra Azul do Norte/GO",
            fonte="Times",
            cabecalho="faixa",
            info="grade",
            titulo="Certificado de Calibração",
            rotulos={
                **_BASICO_PT,
                "numero": "Nº",
                "tipo": "Objeto",
                "codigo": "Código do cliente",
                "faixa": "Capacidade",
                "data_calibracao": "Calibrado em",
                "data_emissao": "Emitido em",
                "temperatura": "Temperatura",
                "umidade": "Umidade",
                "tecnico": "Executado por",
            },
            ordem_info=(
                "tipo", "codigo", "fabricante", "serie", "faixa", "resolucao", "cliente",
                "data_calibracao", "temperatura", "data_emissao", "umidade",
            ),
            colunas=(NOMINAL, ENCONTRADO, ERRO, INCERTEZA),
            titulos_colunas={
                NOMINAL: "VR", ENCONTRADO: "VI", ERRO: "Tendência", INCERTEZA: "U",
            },
            formato_data="extenso",
            decimal=",",
            palavra_faixa="-",
            sinal_mais=True,
            nota="VR = valor de referência; VI = valor indicado. U expandida para k = 2,00.",
            numero=lambda rng, d: f"{rng.randint(1, 99999):05d}/{d.year % 100:02d}",
        ),
        Laboratorio(
            chave="quatro_ventos",
            nome="QUATRO VENTOS CALIBRAÇÕES LTDA",
            endereco="Estrada do Padrão, km 7 - Quatro Ventos/SP",
            fonte="Courier",
            cabecalho="esquerda",
            info="lista",
            titulo="CERTIFICADO DE CALIBRACAO",
            rotulos={
                **_BASICO_PT,
                "numero": "CERTIFICADO",
                "cliente": "SOLICITANTE",
                "tipo": "EQUIPAMENTO",
                "codigo": "TAG",
                "fabricante": "MARCA",
                "serie": "N. SERIE",
                "faixa": "FAIXA",
                "resolucao": "DIV. MINIMA",
                "data_calibracao": "DATA CALIBRACAO",
                "data_emissao": "DATA EMISSAO",
                "temperatura": "TEMP.",
                "umidade": "UR",
                "tecnico": "CALIBRADO POR",
            },
            ordem_info=(
                "cliente", "data_calibracao", "data_emissao", "tipo", "codigo", "fabricante",
                "serie", "faixa", "resolucao", "temperatura", "umidade",
            ),
            colunas=(ENCONTRADO, NOMINAL, ERRO, INCERTEZA, K),
            titulos_colunas={
                ENCONTRADO: "LEITURA", NOMINAL: "PADRAO", ERRO: "DESVIO",
                INCERTEZA: "INC. EXP.", K: "FATOR K",
            },
            formato_data="dd.mm.aaaa",
            decimal=",",
            palavra_faixa="a",
            sinal_mais=True,
            nota="DESVIO = LEITURA - PADRAO. INC. EXP. PARA 95% DE ABRANGENCIA.",
            numero=lambda rng, d: f"QV{rng.randint(1, 999999):06d}",
        ),
        Laboratorio(
            chave="ventania",
            nome="Ventania Metrology Lab",
            endereco="Rua Kelvin, 300 - Porto Ventania/SC - Brasil",
            fonte="Helvetica",
            cabecalho="esquerda",
            info="grade",
            titulo="CERTIFICADO DE CALIBRAÇÃO / CALIBRATION CERTIFICATE",
            rotulos={
                "numero": "Certificado / Certificate No.",
                "cliente": "Cliente / Customer",
                "tipo": "Instrumento / Instrument",
                "codigo": "ID",
                "fabricante": "Fabricante / Manufacturer",
                "serie": "Série / Serial No.",
                "faixa": "Faixa / Range",
                "resolucao": "Resolução / Resolution",
                "data_calibracao": "Data da calibração / Calibration date",
                "data_emissao": "Emissão / Issue date",
                "temperatura": "Temperatura / Temperature",
                "umidade": "Umidade / Humidity",
                "tecnico": "Técnico / Technician",
            },
            ordem_info=(
                "cliente", "tipo", "fabricante", "codigo", "serie", "faixa", "resolucao",
                "data_calibracao", "data_emissao", "temperatura", "umidade",
            ),
            colunas=(NOMINAL, ENCONTRADO, ERRO, INCERTEZA, K),
            titulos_colunas={
                NOMINAL: "Nominal", ENCONTRADO: "Indicação / Reading", ERRO: "Erro / Error",
                INCERTEZA: "U", K: "k",
            },
            formato_data="iso",
            decimal=".",
            palavra_faixa="to",
            sinal_mais=False,
            nota="Expanded uncertainty U = k · uc / Incerteza expandida U = k · uc.",
            numero=lambda rng, d: f"VT-{rng.randint(1, 9999):04d}/{d.year}",
        ),
        Laboratorio(
            chave="bom_sereno",
            nome="Laboratório Bom Sereno de Ensaios e Calibração",
            endereco="Praça do Micrômetro, 8 - Bom Sereno/PR",
            fonte="Times",
            cabecalho="centro",
            info="grade",
            titulo="CERTIFICADO DE CALIBRAÇÃO",
            rotulos={
                **_BASICO_PT,
                "numero": "Número",
                "tipo": "Descrição",
                "codigo": "Identificação do cliente",
                "faixa": "Faixa nominal",
                "resolucao": "Menor divisão",
                "data_calibracao": "Data da calibração",
                "data_emissao": "Data deste certificado",
                "tecnico": "Metrologista",
            },
            ordem_info=(
                "cliente", "data_calibracao", "tipo", "data_emissao", "codigo", "fabricante",
                "faixa", "serie", "resolucao", "temperatura", "umidade",
            ),
            colunas=(INDICE, NOMINAL, ENCONTRADO, ERRO, INCERTEZA),
            titulos_colunas={
                INDICE: "Ponto", NOMINAL: "Referência", ENCONTRADO: "Medido",
                ERRO: "Erro de indicação", INCERTEZA: "U (k=2)",
            },
            formato_data="dd/mmm/aaaa",
            decimal=",",
            palavra_faixa="a",
            sinal_mais=False,
            nota="Os resultados referem-se somente ao item calibrado. U para k = 2.",
            numero=lambda rng, d: f"BS {d.year}{rng.randint(1, 9999):04d}",
        ),
        Laboratorio(
            chave="rio_manso",
            nome="GRUPO RIO MANSO METROLOGIA",
            endereco="Rua do Paralelismo, 77 - Jardim Aferido - Rio Manso/MG",
            fonte="Helvetica",
            cabecalho="centro",
            info="grade",
            titulo="CERTIFICADO DE CALIBRAÇÃO",
            rotulos={
                **_BASICO_PT,
                "numero": "Nº",
                "cliente": "Contratante",
                "tipo": "Descrição",
                "codigo": "Identificação",
                "serie": "N° Série",
                "faixa": "Faixa de indicação",
                "resolucao": "Valor de uma Divisão",
                "data_emissao": "Data da emissão",
                "temperatura": "Temperatura",
                "umidade": "Umidade relativa máxima",
                "tecnico": "Signatário autorizado",
            },
            ordem_info=(
                "data_calibracao", "data_emissao", "cliente", "codigo", "tipo", "faixa",
                "fabricante", "serie", "resolucao", "temperatura", "umidade",
            ),
            colunas=(PARAMETRO, NOMINAL, ENCONTRADO, ERRO, INCERTEZA, K, ERRO_MAXIMO, CRITERIO),
            titulos_colunas={
                PARAMETRO: "Parâmetro", NOMINAL: "Padrão", ENCONTRADO: "Instrumento",
                ERRO: "Erro", INCERTEZA: "Incerteza", K: "k", ERRO_MAXIMO: "Erro\nMáximo",
                CRITERIO: "Critério de\naceitação ±",
            },
            formato_data="dd/mm/aaaa",
            decimal=",",
            palavra_faixa="|",
            sinal_mais=False,
            nota="A incerteza expandida relatada é a incerteza padrão multiplicada pelo fator "
            "de abrangência k (aproximadamente 95%).",
            numero=lambda rng, d: f"{rng.randint(1000000, 9999999)}",
            unidade_em_linha=True,
            frase_criterio="Erro somado à incerteza (Erro máximo) deve ser menor ou igual ao "
            "critério de aceitação adotado pelo cliente: {criterio}",
        ),
    )
}
