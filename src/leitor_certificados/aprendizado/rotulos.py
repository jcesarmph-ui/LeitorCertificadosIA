"""Dá a cada palavra lida a sua resposta certa, usando as caixas do gabarito (etapa 1).

Uma palavra pertence a um campo quando o **centro** dela cai dentro da caixa do campo. Palavra
que não está em nenhuma caixa é "outro" (rótulos, endereço, título, observações…).
"""

from __future__ import annotations

from ..leitura import Pagina

OUTRO = "outro"


def rotular(pagina: Pagina, campos: list[dict], folga: float = 0.0) -> list[str]:
    """Um rótulo por palavra, na mesma ordem de `pagina.palavras`.

    `folga` alarga as caixas (no escaneado a caixa e o OCR nunca batem exatamente).
    """
    rotulos: list[str] = []
    for palavra in pagina.palavras:
        cx, cy = palavra.centro
        rotulo = OUTRO
        for campo in campos:
            esq, topo, dir_, base = campo["caixa"]
            if esq - folga <= cx <= dir_ + folga and topo - folga <= cy <= base + folga:
                rotulo = campo["campo"]
                break
        rotulos.append(rotulo)
    return rotulos
