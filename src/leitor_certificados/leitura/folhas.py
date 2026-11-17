"""PDF com mais de uma folha (etapa 12): as folhas usadas viram uma "folha comprida".

Só entram as folhas necessárias (a 1ª sempre; outra só se tiver pontos ou padrões que faltaram,
decisão do usuário de 2026-11-17). Elas ficam uma embaixo da outra, com a mesma altura: a folha
`k` (de `n`) ocupa a faixa `k/n` a `(k+1)/n` da altura. Assim a tela, as correções e os checks
continuam tratando uma página só.

O modelo, porém, aprendeu com uma folha de cada vez (a posição "y" é uma pista). Por isso ele
olha cada folha separada, de volta na medida dela (`separar`).
"""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image

from .palavra import Pagina, Palavra


def juntar(paginas: Sequence[Pagina], folhas: Sequence[int]) -> Pagina:
    """Junta as páginas lidas (na ordem) numa folha comprida. `folhas` = o número de cada uma
    no PDF (0 = a 1ª). A rotação que vale é a da 1ª (escaneado virado afeta o PDF todo)."""
    if len(paginas) == 1:
        unica = paginas[0]
        return Pagina(unica.origem, list(unica.palavras), unica.rotacao, tuple(folhas))
    n = len(paginas)
    palavras = [
        Palavra(p.texto, (p.caixa[0], (k + p.caixa[1]) / n, p.caixa[2], (k + p.caixa[3]) / n),
                p.confianca)
        for k, pagina in enumerate(paginas) for p in pagina.palavras
    ]
    origem = "ocr" if any(p.origem == "ocr" for p in paginas) else "digital"
    return Pagina(origem, palavras, paginas[0].rotacao, tuple(folhas))


def faixa_da_palavra(palavra: Palavra, n: int) -> int:
    """Em qual folha (0 a n−1) da folha comprida a palavra está."""
    return min(int(palavra.centro[1] * n), n - 1)


def separar(pagina: Pagina) -> list[tuple[Pagina, list[int]]]:
    """O contrário de `juntar`: cada folha com as palavras na medida dela e, junto, o índice de
    cada palavra na folha comprida (para pôr a resposta do modelo no lugar certo)."""
    n = len(pagina.folhas)
    if n <= 1:
        return [(pagina, list(range(len(pagina.palavras))))]
    grupos: list[tuple[list[Palavra], list[int]]] = [([], []) for _ in range(n)]
    for i, p in enumerate(pagina.palavras):
        k = faixa_da_palavra(p, n)
        grupos[k][0].append(Palavra(
            p.texto, (p.caixa[0], p.caixa[1] * n - k, p.caixa[2], p.caixa[3] * n - k),
            p.confianca))
        grupos[k][1].append(i)
    return [(Pagina(pagina.origem, palavras, pagina.rotacao, (pagina.folhas[k],)), indices)
            for k, (palavras, indices) in enumerate(grupos)]


def empilhar(imagens: Sequence[Image.Image]) -> Image.Image:
    """As imagens das folhas uma embaixo da outra, todas com a largura e a altura da 1ª (as
    caixas são frações da altura de cada folha)."""
    if len(imagens) == 1:
        return imagens[0]
    largura, altura = imagens[0].size
    junta = Image.new("RGB", (largura, altura * len(imagens)), "white")
    for k, imagem in enumerate(imagens):
        junta.paste(imagem.convert("RGB").resize((largura, altura)), (0, k * altura))
    return junta


def cortar(imagem: Image.Image, n: int) -> list[Image.Image]:
    """O contrário de `empilhar` para uma camada desenhada sobre a folha comprida (checks):
    um pedaço para cada folha."""
    if n <= 1:
        return [imagem]
    altura = imagem.height / n
    return [imagem.crop((0, round(k * altura), imagem.width, round((k + 1) * altura)))
            for k in range(n)]
