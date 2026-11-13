# 0009 — Colunas "Erro Máximo" e "Critério de aceitação ±": ler e comparar com o plano

**Data:** 2026-11-13 · **Situação:** aceita

## Contexto
Alguns laboratórios trazem, além de nominal, encontrado, erro, incerteza e k, duas colunas a mais:
- **Erro Máximo**: o erro somado à incerteza (|erro| + U), já calculado pelo laboratório;
- **Critério de aceitação ±**: o limite que **o cliente** informou ao laboratório.

O modelo não conhecia essas colunas e as confundia com a incerteza: os números são parecidos,
positivos e pequenos. Nenhum laboratório fictício tinha essas colunas, então o modelo nunca as
tinha visto. O critério, além disso, é uma informação útil: se não for o mesmo do plano, o
laboratório julgou o instrumento com outra régua.

## Decisão
- **Laboratório fictício novo** (`rio_manso`, nome e endereço inventados) no estilo dessas folhas:
  coluna de texto "Parâmetro", unidade numa linha própria embaixo dos títulos, títulos em duas
  linhas, colunas `ponto.erro_maximo` e `ponto.criterio` e a frase do critério acima da tabela.
  Em metade dos planos fictícios dele a tolerância é igual ao critério e na outra metade é
  diferente, para testar os dois casos.
- **Pista nova para o modelo**: "este número é |um número da linha| + outro positivo?" (`e_soma_abs`),
  que é a definição do erro máximo e vale para qualquer laboratório.
- **Comparação só avisa** (decisão do usuário, opção "b"): o critério ± c do certificado é
  comparado com a tolerância do plano; é igual só quando o plano vai de −c a +c. Se for
  diferente, aparece **um aviso amarelo** (um só para os pontos com a mesma diferença), e a
  coluna "Critério" da tabela fica amarela. **O parecer não muda**: continua vindo da regra
  erro ± U contra a tolerância do plano (ADR 0006), igual à faixa.
- A coluna "Critério" da tela **só aparece** quando o certificado tem critério.

## Consequências
- Os certificados fictícios mudam (o sorteio passa a ter 6 laboratórios): medidas antigas não
  são comparáveis número a número; as novas estão no README.
- O escaneado real do mesmo laboratório usa um modelo de folha antigo, **sem** essas colunas:
  a melhora vale para a folha digital.
- O "Erro Máximo" é lido mas ainda não é conferido (|erro| + U = erro máximo?); fica para depois,
  se fizer falta.
