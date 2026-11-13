# 0007 — Aprender com o uso: o modelo melhora com certificados reais corrigidos

**Data:** 2026-11-12 · **Situação:** aceita

## Contexto
O modelo da etapa 3 foi treinado só com certificados fictícios e, em laboratório que nunca viu,
acerta bem menos (ADR 0005, ADR 0006). Os certificados reais vêm de vários laboratórios, com
tabelas diferentes (colunas "Erro Máximo" e "Critério de aceitação", leituras 01/02/03, média,
tendência…). Tentar prever todos os formatos de antemão não é realista; o objetivo do programa é
**comparar o certificado com o plano** (código, faixa e principalmente tolerância).

## Decisão
- **Aprender com a correção humana**: o programa mostra o que leu (palavra a palavra, com a
  certeza do modelo); a pessoa corrige o rótulo onde errou; o modelo é retreinado com os
  fictícios **mais** os reais corrigidos, e cada real conta como 5 fictícios (`PESO_REAL`).
- **A correção é um arquivo simples** (`<nome>.palavras.json`, campo `certo`), editável por
  `scripts/corrigir_reais.py` (por número ou faixa) e conferível em foto (`scripts/foto_revisao.py`).
  Reais e modelos treinados com eles ficam só no PC, fora do Git (ADR 0002).
- **Medir com "deixa um de fora"** (`scripts/medir_aprendizado.py`): treina sem um certificado real
  e testa nele, com 0, 1, 2 e 3 outros reais corrigidos. A medida principal é a dos **essenciais**
  para a comparação com o plano — código, faixa, nominal, encontrado, erro e incerteza; fabricante,
  laboratório e técnico são secundários.
- **Rótulos novos quando o formato pede** (`ponto.erro_maximo`, `ponto.criterio`), sem mexer no
  que já funcionava.

## Consequências
Média nos 4 certificados reais, cada um deixado de fora (60 fictícios no treino):

| Reais corrigidos no treino | Essenciais certos | Outros campos | "Falsos" (ruído)* |
|---|---|---|---|
| nenhum (só fictícios) | 70,2 % | 30,2 % | 75,0 |
| 1 | 83,0 % | 40,7 % | 38,8 |
| 2 | 89,2 % | 51,3 % | 31,6 |
| 3 | 91,5 % | 58,1 % | 29,8 |

<sub>*Palavras "outro" que o modelo marcou como campo, por certificado.</sub>

- **A cada real corrigido o acerto sobe e o ruído cai**; o programa aprende com o uso.
- **Cuidado ao ler a tabela**: dois dos 4 reais são do mesmo laboratório (digital e escaneado), então
  um ajuda o outro; os de laboratório único (balanças e durômetro) também melhoram (65 % → 83 % e
  49 % → 90 % nos essenciais), mas com poucos exemplos a medida é grosseira.
- **Defeito achado pela medida**: a detecção de folha invertida (etapa 2) era enganada pelo carimbo
  "ESTE CERTIFICADO FOI ANALISADO" no alto da folha de cabeça para baixo, e o modelo via o título
  das colunas embaixo dos números. Agora só "CERTIFICADO DE…" conta como título; esse escaneado
  passou de ~30 % para 96 % nos essenciais.
- **Lacuna conhecida**: a conferência ainda não compara a **faixa** do certificado com a do plano.
- Próximos passos: limiar de certeza (palavra incerta vira "outro"/"revisar") e a interface para
  corrigir e reaprender pela tela.
