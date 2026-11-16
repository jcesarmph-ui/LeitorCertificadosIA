# 0010 — Validade dos padrões no dia da calibração

**Data:** 2026-11-16 · **Situação:** aceita

## Contexto
O certificado de calibração traz a tabela dos **padrões** que o laboratório usou (código,
descrição, certificado do padrão e validade). Se um padrão já estava **vencido no dia da
calibração**, a medição não tem rastreabilidade garantida, mesmo que todos os pontos passem na
tolerância. Hoje isso é conferido de olho; o leitor não olhava a tabela.

Nos certificados reais apareceram três jeitos de escrever a tabela e duas armadilhas:
- código do padrão + "Descrição - Certificado" + validade só com **mês e ano** ("04/2027");
- padrão identificado pelo **número do certificado** dele, com validade em data completa;
- armadilha 1: "Validade: 08/2027" no topo da folha é a validade **do certificado**, não de um
  padrão;
- armadilha 2: a coluna "Data da Calibração" **do padrão** não é a data da calibração do
  instrumento.

## Decisão
- **Dois rótulos novos** para o modelo: `padrao.codigo` (o código, ou o nº do certificado
  quando o laboratório não dá código) e `padrao.validade`. A data da calibração do instrumento
  já era um rótulo (`data_calibracao`).
- **Gerador fictício** (versão 3): os 6 laboratórios inventados ganham tabelas de padrões
  diferentes (títulos, ordem das colunas, validade em mês/ano, por extenso, ISO e dd/mm/aaaa),
  1 a 5 padrões cada, ~12 % com um padrão vencido, e as duas armadilhas acima. O gabarito diz
  se cada padrão estava vencido.
- **Regra** (`conferencia/padroes.py`, decisões do usuário):
  - validade "07/2026" vale **o mês inteiro** (até 31/07/2026);
  - padrão **vencido** no dia da calibração → se os pontos passam, parecer **PENDENTE** (alguém
    precisa olhar antes de aceitar o certificado); se os pontos reprovam, continua
    **REPROVADO**. Em todos os casos o **motivo** aparece em vermelho no parecer (qual padrão, a
    validade e a data da calibração; e quais pontos ficaram fora da tolerância);
  - validade não lida, data da calibração não lida ou tabela não encontrada → **só aviso
    amarelo**; o parecer não muda.
- A data da calibração pode ser **digitada à mão** (Corrigir → Digitar à mão), como o código e a
  faixa.
- **Tela**: caixa "Padrões" ao lado de "Instrumento" (data da calibração + cada padrão com
  "✓ em dia" em verde, "✗ VENCIDO" em vermelho ou "não conferido" em amarelo) e, na folha, uma
  marca redonda ao lado de cada linha de padrão, nas mesmas cores, igual aos checks dos pontos.
  No parecer, os motivos de problema ficam em vermelho e os avisos em amarelo.
- **Reais**: as correções já gravadas marcavam essas palavras como "outro" e pesam 5 vezes no
  treino; sem acertá-las, o modelo desaprenderia os padrões. Um script fora do Git só
  **acrescenta** as marcações de padrão (nada mais muda), com cópia de antes e foto de revisão.

## Consequências
- Os certificados fictícios mudam (gerador versão 3): o lote é refeito sozinho na próxima vez.
- Um certificado com padrão vencido nunca sai "APROVADO" sem alguém olhar, e o reprovado
  continua reprovado, com os dois motivos à vista.
- Certificado sem tabela de padrões (ex.: o do durômetro real) recebe o aviso amarelo "padrões
  não encontrados". Tabela numa segunda página ainda não é lida: nesta versão o leitor só olha
  a primeira página.
