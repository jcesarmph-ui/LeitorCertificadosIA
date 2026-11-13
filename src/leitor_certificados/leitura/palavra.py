"""O formato comum da leitura: uma página é uma lista de palavras com posição.

A posição usa a mesma medida do gabarito (etapa 1): **fração da página**, de 0 a 1, contando a
partir do canto de cima à esquerda — `[esquerda, topo, direita, base]`. Assim tanto faz o tamanho
da folha ou a resolução do scanner: "0.5" é sempre o meio.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palavra:
    texto: str
    caixa: tuple[float, float, float, float]  # esquerda, topo, direita, base (fração da página)
    confianca: float = 1.0  # 1.0 no digital (o texto é exato); no OCR, a certeza de 0 a 1

    @property
    def centro(self) -> tuple[float, float]:
        return (self.caixa[0] + self.caixa[2]) / 2, (self.caixa[1] + self.caixa[3]) / 2


@dataclass
class Pagina:
    origem: str  # "digital" ou "ocr"
    palavras: list[Palavra] = field(default_factory=list)

    def texto_na_caixa(self, caixa: list[float] | tuple[float, ...], folga: float = 0.0) -> str:
        """Junta, na ordem de leitura, as palavras cujo centro está dentro da caixa."""
        esq, topo, dir_, base = caixa
        dentro = [
            p for p in self.palavras
            if esq - folga <= p.centro[0] <= dir_ + folga
            and topo - folga <= p.centro[1] <= base + folga
        ]
        dentro.sort(key=lambda p: p.caixa[0])
        return " ".join(p.texto for p in dentro)
