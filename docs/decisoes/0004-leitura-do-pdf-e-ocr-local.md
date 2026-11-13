# 0004 — Leitura do PDF: texto direto quando existe, OCR local quando é só imagem

**Data:** 2026-11-11 · **Situação:** aceita

## Contexto
A etapa 3 (machine learning) precisa receber a folha como uma lista de **palavras com posição**,
igual nos dois tipos de PDF. Os certificados chegam digitais (com texto dentro) e escaneados (só
uma foto). Tudo tem de rodar neste computador e de graça (ADR 0001).

## Decisão
- **Formato comum**: `Pagina` com `Palavra`s (texto, caixa em fração da folha — a mesma medida do
  gabarito —, confiança). O modelo não precisa saber de onde a palavra veio.
- **Digital**: lê as letras e a posição direto do PDF (pypdfium2) e junta em palavras. Exato, 0,01 s.
- **Escaneado**: **RapidOCR** (modelos ONNX, licença Apache 2.0, rodam no computador, sem internet).
  A página vira imagem a 200 dpi antes do OCR. Cada palavra guarda a **confiança** do OCR.
- **Porta de entrada `ler_pdf`**: escolhe o caminho **por página** (tem texto → direto; só imagem
  → OCR), porque um mesmo PDF pode misturar os dois.
- Correções só onde não mudam o que está escrito: `℃` → `°C` e separar "ROTULO:resposta" grudado.
- O OCR só é carregado quando uma página precisa dele (demora alguns segundos para abrir).

## Consequências
- Digital: 100 % das respostas certas em 30 fictícios. Escaneado: cerca de 98 % — os erros são
  principalmente números pequenos da tabela (vírgula lida como apóstrofo) e nome do laboratório
  grudado no endereço. Esses erros chegam à etapa 3, que deve usar a confiança.
- O escaneado de um scanner real (150 dpi, mais texto por folha) é **mais difícil** que os
  fictícios: a confiança média do OCR foi bem menor. Por isso o gerador passou a usar 150 dpi na
  maioria dos escaneados, com mais ruído e desfoque. A etapa 5 mostra o acerto nos reais.
- Ampliar a imagem (300 dpi) melhora a leitura do escaneado real; fica como ajuste a testar.
