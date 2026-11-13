"""Sorteia o conteúdo de um certificado fictício — e esse conteúdo é o próprio gabarito.

Tudo é inventado: instrumento, código, fabricante, cliente, técnico, datas e medições.
O sorteio usa um `random.Random` com **semente**: a mesma semente gera sempre o mesmo
certificado. Isso permite repetir o treino e os testes e comparar resultados de forma justa.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .laboratorios import CRITERIO, LABORATORIOS, Laboratorio


@dataclass(frozen=True)
class ModeloInstrumento:
    tipo: str
    sigla: str  # inventada (não é o padrão de códigos de nenhuma empresa real)
    unidade: str
    faixas: tuple[tuple[float, float], ...]
    resolucoes: tuple[float, ...]


INSTRUMENTOS = (
    ModeloInstrumento("Paquímetro", "PQ", "mm", ((0, 150), (0, 200), (0, 300)), (0.01, 0.02, 0.05)),
    ModeloInstrumento(
        "Micrômetro externo", "MC", "mm", ((0, 25), (25, 50), (50, 75)), (0.001, 0.01)
    ),
    ModeloInstrumento("Trena", "TR", "mm", ((0, 3000), (0, 5000)), (1.0,)),
    ModeloInstrumento("Manômetro", "MN", "bar", ((0, 10), (0, 16), (0, 25)), (0.1, 0.2, 0.5)),
    ModeloInstrumento("Termômetro digital", "TD", "°C", ((-20, 150), (0, 200)), (0.1,)),
    ModeloInstrumento("Relógio comparador", "RC", "mm", ((0, 10),), (0.01, 0.001)),
)

FABRICANTES = ("Metrovix", "Exatron", "Pramezzi", "Kalibrik", "Tessmar", "Nordavel", "Quiron")
CLIENTES = (
    "Indústria Modelo Ltda",
    "Usinagem Exemplo S.A.",
    "Fundição Fictícia Ltda",
    "Caldeiraria Demonstração Ltda",
    "Montagens Imaginárias Ltda",
)
NOMES = ("Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gisele", "Hugo", "Íris", "Júlio")
SOBRENOMES = ("Andrade", "Barreto", "Campos", "Duarte", "Esteves", "Freitas", "Guedes", "Horta")

INICIO = date(2024, 1, 1)
FIM = date(2026, 10, 31)


@dataclass
class Ponto:
    nominal: float  # valor de referência (o que o padrão do laboratório marca)
    encontrado: float  # o que o instrumento do cliente indicou
    erro: float  # encontrado − nominal
    incerteza: float  # incerteza expandida U
    k: float  # fator de abrangência
    # só nos laboratórios que trazem estas colunas (ADR 0009); nos outros fica None
    erro_maximo: float | None = None  # |erro| + U
    criterio: float | None = None  # critério de aceitação ± do cliente
    parametro: str | None = None  # o que foi medido na linha ("Face externa"…)


@dataclass
class Certificado:
    id: str
    laboratorio: str  # chave em LABORATORIOS
    numero: str
    data_calibracao: date
    data_emissao: date
    cliente: str
    tipo: str
    codigo: str
    fabricante: str
    serie: str
    faixa_min: float
    faixa_max: float
    resolucao: float
    unidade: str
    casas: int  # casas decimais dos valores (as da resolução)
    temperatura: float
    umidade: int
    tecnico: str
    pontos: list[Ponto]

    @property
    def lab(self) -> Laboratorio:
        return LABORATORIOS[self.laboratorio]

    def para_dict(self) -> dict:
        d = asdict(self)
        d["data_calibracao"] = self.data_calibracao.isoformat()
        d["data_emissao"] = self.data_emissao.isoformat()
        return d


def casas_decimais(resolucao: float) -> int:
    texto = f"{resolucao:.6f}".rstrip("0").rstrip(".")
    return len(texto.split(".")[1]) if "." in texto else 0


def _pontos(rng: random.Random, modelo: ModeloInstrumento, minimo: float, maximo: float,
            resolucao: float, casas: int, lab: Laboratorio) -> list[Ponto]:
    # Pontos "redondos", como nos certificados de verdade (0, 50, 100… e não 36,7):
    # o passo é 1, 2, 2,5 ou 5 vezes uma potência de 10, com 4 a 11 pontos na faixa.
    passos = [
        m * 10**e for e in range(-3, 4) for m in (1, 2, 2.5, 5)
        if 3 <= (maximo - minimo) / (m * 10**e) <= 10 and m * 10**e >= resolucao
    ]
    exatos = [s for s in passos if abs((maximo - minimo) / s - round((maximo - minimo) / s)) < 1e-9]
    passo = rng.choice(exatos or passos)
    # Começo e fim da faixa sempre entram; no meio, os múltiplos redondos do passo.
    nominais = [round(minimo, casas)]
    valor = math.floor(minimo / passo + 1e-9) * passo + passo
    while valor < maximo - 1e-9:
        nominais.append(round(valor, casas))
        valor += passo
    nominais.append(round(maximo, casas))
    # Fator k: quem não tem coluna "k" declara k = 2 na observação.
    tem_k = "k" in lab.colunas
    # Critério de aceitação: um só para o certificado inteiro, algumas divisões de resolução.
    criterio = None
    if CRITERIO in lab.colunas:
        criterio = round(resolucao * rng.choice((2, 3, 5, 5, 10)), casas)
    parametros = (("Face Externa",) * 4 + ("Face Interna", "Bico Interno/Externo")
                  if modelo.tipo == "Paquímetro" else ("Leitura",))
    pontos = []
    for nominal in nominais:
        # Erro: quase sempre poucas divisões; às vezes um erro maior (instrumento ruim).
        divisoes = rng.choice((-2, -1, -1, 0, 0, 0, 1, 1, 2)) if rng.random() < 0.9 \
            else rng.randint(-8, 8)
        encontrado = round(nominal + divisoes * resolucao, casas)
        erro = round(encontrado - nominal, casas)
        incerteza = round(resolucao * rng.uniform(0.6, 2.5), casas + 1)
        incerteza = max(incerteza, 10 ** -(casas + 1))
        k = rng.choice((2.0, 2.0, 2.0, 2.03, 2.05, 2.11)) if tem_k else 2.0
        ponto = Ponto(nominal, encontrado, erro, incerteza, k)
        if criterio is not None:
            ponto.erro_maximo = round(abs(erro) + incerteza, casas + 1)
            ponto.criterio = criterio
            ponto.parametro = rng.choice(parametros)
        pontos.append(ponto)
    return pontos


def sortear_certificado(rng: random.Random, ident: str) -> Certificado:
    """Inventa um certificado completo. O que for sorteado aqui é a resposta certa (gabarito)."""
    lab = rng.choice(list(LABORATORIOS.values()))
    modelo = rng.choice(INSTRUMENTOS)
    minimo, maximo = rng.choice(modelo.faixas)
    resolucao = rng.choice(modelo.resolucoes)
    casas = casas_decimais(resolucao)
    data_cal = INICIO + timedelta(days=rng.randint(0, (FIM - INICIO).days))
    return Certificado(
        id=ident,
        laboratorio=lab.chave,
        numero=lab.numero(rng, data_cal),
        data_calibracao=data_cal,
        data_emissao=data_cal + timedelta(days=rng.randint(0, 10)),
        cliente=rng.choice(CLIENTES),
        tipo=modelo.tipo,
        codigo=f"{modelo.sigla}-{rng.randint(1, 9999):04d}",
        fabricante=rng.choice(FABRICANTES),
        serie=f"{rng.choice('ABCDEFGHJK')}{rng.randint(10000, 999999)}",
        faixa_min=float(minimo),
        faixa_max=float(maximo),
        resolucao=resolucao,
        unidade=modelo.unidade,
        casas=casas,
        temperatura=round(rng.uniform(19.0, 23.0), 1),
        umidade=rng.randint(35, 65),
        tecnico=f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}",
        pontos=_pontos(rng, modelo, minimo, maximo, resolucao, casas, lab),
    )
