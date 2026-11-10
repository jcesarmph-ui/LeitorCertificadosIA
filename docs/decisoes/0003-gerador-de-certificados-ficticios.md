# 0003 — Gerador de certificados fictícios com gabarito anotado

**Data:** 2026-11-10 · **Situação:** aceita

## Contexto
O modelo precisa de muitos exemplos **com a resposta certa** para aprender e para ser medido
(ADR 0001), e o repositório só pode ter certificados inventados (ADR 0002). Os certificados reais
do autor são de vários laboratórios e chegam **digitais e escaneados**.

## Decisão
- **Vários laboratórios inventados** (5 na etapa 1), cada um com o seu modelo de folha: fonte,
  cabeçalho, ordem e nome das informações, ordem e nome das colunas, formato de data (5 tipos),
  vírgula ou ponto decimal, numeração própria. Assim o modelo não pode "decorar" posições.
- **Gabarito anotado**: além dos valores certos, cada texto que é uma resposta (nº, data,
  laboratório, código, valores de cada ponto…) tem a sua **caixa** na página, em fração da folha.
  É o que permite, na etapa 3, ensinar o modelo a reconhecer cada pedaço de texto.
- **"Escaneado" imitado**: a página vira imagem (150/200 dpi), gira até 1,5°, desloca, ganha
  ruído, desfoque e compressão JPEG, e é salva como PDF **sem texto**. As caixas do gabarito são
  giradas junto.
- **Semente**: cada certificado tem a sua (`2026-<número>`); gerar de novo dá o mesmo arquivo.
- Bibliotecas gratuitas e locais: **reportlab** (escreve PDF), **pypdfium2** (PDF → imagem e
  leitura de texto, licença Apache/BSD), **Pillow** (efeitos de scanner).
- Todo certificado diz no rodapé que é **fictício e sem validade**.

## Consequências
- Dá para gerar centenas de exemplos em segundos e medir o acerto com justiça (treino × teste).
- Fictícios são mais "limpos" que os reais: o acerto com reais (etapa 5) deve ser menor, e isso
  será mostrado.
- Testes automáticos conferem no próprio PDF que cada resposta está dentro da sua caixa.
