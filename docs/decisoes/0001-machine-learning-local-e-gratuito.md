# 0001 — Machine learning local e gratuito (scikit-learn), sem IA paga

**Data:** 2026-11-10 · **Situação:** aceita

## Contexto
O objetivo é ler certificados de calibração em PDF (digitais e escaneados), achar os dados
importantes (nº do certificado, data, laboratório, pontos com valor nominal, valor encontrado e
incerteza U) e conferir com o plano de calibração. É um projeto de **estudo e portfólio**: o autor
quer **aprender** como um modelo de machine learning é treinado, testado e medido.

Uma IA paga por uso (modelos de linguagem na nuvem) foi descartada: só interessaria se fosse de
graça, e mandar certificados reais para um serviço externo não é aceitável.

## Decisão
- **scikit-learn** (gratuito, roda no próprio computador): modelos clássicos e explicáveis, bons
  para aprender (treino × teste, acerto, matriz de confusão, por que o modelo errou).
- **OCR gratuito e local** para os PDFs escaneados (escolhido na etapa de leitura).
- Nenhum dado sai do computador.

## Consequências
- O acerto será menor que o de uma IA grande — e **está tudo bem**: o projeto mede e mostra a
  evolução do acerto, que é o que interessa no portfólio.
- Dá para explicar cada passo, o que uma "caixa-preta" paga não permitiria.
