"""As cores das caixas por rótulo na folha — quatro opções para o usuário escolher.

Regra que guia todas: as caixas dos campos NÃO usam verde, vermelho nem amarelo fortes. Essas
três cores têm significado no padrão do usuário (certo / erro / aviso) e são as cores dos checks
da conferência; se as caixas também as usassem, os checks se perderiam no meio delas.

Para trocar a paleta do programa, mude só `PALETA_ATUAL`.
"""

from __future__ import annotations

from dataclasses import dataclass

Cor = tuple[int, int, int]


@dataclass(frozen=True)
class Paleta:
    nome: str
    descricao: str
    cores: dict[str, Cor]  # rótulo → cor (os que faltam usam `padrao`)
    padrao: Cor
    preencher: bool = True  # False = só o contorno (a folha fica mais limpa)


# Rótulos agrupados como aparecem na legenda (as duas datas têm a mesma cor).
LEGENDA: list[tuple[str, list[str]]] = [
    ("Valor nominal", ["ponto.nominal"]),
    ("Valor encontrado", ["ponto.encontrado"]),
    ("Erro", ["ponto.erro"]),
    ("Incerteza (U)", ["ponto.incerteza"]),
    ("k", ["ponto.k"]),
    ("Erro máximo", ["ponto.erro_maximo"]),
    ("Critério de aceitação", ["ponto.criterio"]),
    ("Código do instrumento", ["codigo"]),
    ("Faixa", ["faixa"]),
    ("Tipo", ["tipo"]),
    ("Fabricante", ["fabricante"]),
    ("Nº de série", ["serie"]),
    ("Resolução", ["resolucao"]),
    ("Datas", ["data_calibracao", "data_emissao"]),
    ("Cliente", ["cliente"]),
    ("Laboratório", ["laboratorio"]),
    ("Técnico", ["tecnico"]),
    ("Temperatura", ["temperatura"]),
    ("Umidade", ["umidade"]),
    ("Nº do certificado", ["numero_certificado"]),
]
REVISAR = "Revisar (certeza baixa)"


def _por_grupo(cores_da_legenda: list[Cor]) -> dict[str, Cor]:
    """Liga cada cor, na ordem da LEGENDA, aos rótulos daquele grupo."""
    cores: dict[str, Cor] = {}
    for (_, rotulos), cor in zip(LEGENDA, cores_da_legenda, strict=True):
        for rotulo in rotulos:
            cores[rotulo] = cor
    return cores


PALETAS: dict[str, Paleta] = {
    # A — tons frios e pastel (azuis, roxos, cianos, rosas), só no contorno
    "A": Paleta("frios_pastel", "Tons frios e pastel, só no contorno", _por_grupo([
        (66, 133, 244), (0, 172, 193), (149, 117, 205), (236, 64, 160), (121, 134, 203),
        (186, 104, 200), (77, 182, 172), (30, 136, 229), (92, 107, 192), (126, 87, 194),
        (144, 164, 174), (100, 181, 246), (128, 222, 234), (240, 98, 146), (171, 71, 188),
        (120, 144, 156), (159, 168, 218), (79, 195, 247), (38, 198, 218), (206, 147, 216),
    ]), padrao=(144, 164, 174), preencher=False),
    # B — cinzas, com um único destaque azul para os valores da tabela de pontos
    "B": Paleta("cinza_azul", "Cinzas; só a tabela de pontos em azul", _por_grupo(
        [(25, 118, 210)] * 7 + [(55, 71, 79)] + [(110, 110, 110)] * 12,
    ), padrao=(140, 140, 140)),
    # C — cores vivas, mas fora de verde/vermelho/amarelo
    "C": Paleta("vivas", "Vivas: azul, ciano, magenta, roxo, laranja-queimado, marrom",
                _por_grupo([
                    (21, 101, 192), (0, 151, 167), (142, 36, 170), (216, 27, 96),
                    (94, 53, 177), (200, 90, 20), (109, 76, 65), (40, 53, 147), (0, 131, 143),
                    (121, 85, 72), (84, 110, 122), (57, 73, 171), (2, 119, 189),
                    (173, 20, 87), (106, 27, 154), (69, 90, 100), (123, 31, 162),
                    (1, 87, 155), (0, 96, 100), (136, 14, 79),
                ]), padrao=(84, 110, 122)),
    # D — acessível para daltônicos (Okabe-Ito sem o verde, o vermelhão e o amarelo)
    "D": Paleta("daltonicos", "Okabe-Ito (acessível a daltônicos), sem verde/vermelho/amarelo",
                _por_grupo([
                    (0, 114, 178), (86, 180, 233), (230, 159, 0), (204, 121, 167),
                    (0, 0, 0), (230, 159, 0), (204, 121, 167), (0, 0, 0), (0, 114, 178),
                    (86, 180, 233), (120, 120, 120), (120, 120, 120), (120, 120, 120),
                    (204, 121, 167), (120, 120, 120), (120, 120, 120), (120, 120, 120),
                    (86, 180, 233), (86, 180, 233), (0, 114, 178),
                ]), padrao=(120, 120, 120)),
}

# E — tudo azul (escolha do usuário em 2026-11-12): a cor não separa os campos; o tipo de
# cada valor aparece na dica do mouse. Sem legenda (seria uma cor só).
PALETAS["E"] = Paleta("azul", "Todas as caixas azuis; o tipo aparece na dica do mouse", {},
                      padrao=(25, 118, 210))

PALETA_ATUAL = "E"


def paleta() -> Paleta:
    return PALETAS[PALETA_ATUAL]


def cor_rgb(rotulo: str) -> Cor:
    atual = paleta()
    return atual.cores.get(rotulo, atual.padrao)
