# 0011 — Conferência de conta, goniômetro em graus e minutos e mais certificados reais

**Data:** 2026-11-16 · **Situação:** aceita

## Contexto
Com mais certificados reais corrigidos do laboratório principal (de 5 para 11, entre eles 3 goniômetros), a
medida mostrou um caso que **não melhorava**: o goniômetro. Investigando, o erro não era do
modelo (com o goniômetro no treino, todas as colunas saíam certas), e sim do que vinha depois:

- o laboratório escreve o erro do goniômetro como **Instrumento − Padrão**, o contrário de
  "encontrado − nominal". O programa achava que as colunas estavam trocadas, "reatribuía" sozinho
  e escolhia o número do **Quadrante** (1, 2, 3, 4) como erro — e **reprovava um goniômetro
  aprovado**;
- a palavra **"Padrão"** quer dizer coisas opostas: no paquímetro é o nominal, no goniômetro é o
  valor encontrado;
- um dos goniômetros escreve os ângulos em **graus e minutos** ("14°59'"), que o programa não
  entendia como número;
- o código pode vir com menos zeros ("GON-02" no certificado, "GON-002" no cadastro).

## Decisão
- **Conferência de conta** em cada ponto (decisão do usuário): o erro tem de fechar com
  encontrado − nominal, **em qualquer um dos dois sinais** (quem declara o sinal é o laboratório);
  com a coluna "Erro Máximo", |erro| + U tem de dar esse valor. Se os números da linha não fecham
  a conta nem trocando as colunas, o ponto fica **não avaliado** (aviso amarelo, parecer
  PENDENTE): **nunca aprova nem reprova com um número que não fecha**.
- **Graus e minutos** (usuário: "no goniômetro é sempre assim"): "14°59'" = 14 graus e 59
  minutos. A conta é feita em graus decimais; a **tela mostra igual ao certificado** (90°00',
  erro 0°04'). A tolerância do plano ("± 0,25°") é em **graus decimais** (= 0°15').
- O modelo ganhou a pista **"graus e minutos"**: "14°59'" entra nas pistas como o número 14,983.
- **Código**: zeros à esquerda do número não contam ("GON-02" = "GON-002"), só quando há um único
  instrumento possível. Se houver dúvida entre dois, vale o único cujo **plano tem todos os pontos
  nominais** do certificado (ideia do usuário); senão, não escolhe.
- O programa **treina de novo sozinho** ao abrir quando o modelo salvo é mais velho que as
  correções ou não conhece algum rótulo delas (o modelo de 13/11 nem conhecia os padrões).
- Na tela, os avisos do parecer têm **rolagem própria** (altura máxima) e o painel tem rolagem
  geral: muitos avisos não roubam mais o espaço da tabela de pontos.

## Consequências
- Goniômetro real: de REPROVADO por engano para APROVADO; o goniômetro em graus e minutos,
  escondido do treino, foi de 11 % para 100 % dos dados essenciais (com os outros 10 reais).
- Mais pontos podem ficar "não avaliado" quando o modelo erra uma coluna: é de propósito — o
  certo é alguém conferir, e a correção ensina o modelo.
- Ainda pendente: o leitor só lê a primeira página (o goniômetro tem 2; a tabela está na 1ª).
