# 0005 — Machine learning: classificar cada palavra, medindo em laboratório que o modelo nunca viu

**Data:** 2026-11-11 · **Situação:** aceita

## Contexto
A etapa 2 entrega a folha como lista de palavras com posição. A etapa 3 precisa dizer **o que cada
palavra é** (número do certificado, data, valor de cada ponto…) e provar que o modelo **aprendeu**,
e não decorou. Os certificados reais têm vários modelos de laboratório e novos tipos vão aparecer.

## Decisão
- **Uma classificação por palavra**: cada palavra recebe um rótulo do gabarito (ou "outro"), pelo
  centro dela dentro da caixa do gabarito. Os campos são montados juntando as palavras de cada rótulo.
- **Modelo simples e explicável**: `DictVectorizer` + `LogisticRegression` (scikit-learn). Testamos
  também florestas de árvores: não ganharam de forma clara e são mais difíceis de explicar.
- **Pistas de entendimento, não de posição**: jeito do texto (dígitos, vírgula, barra), palavras e
  **pedaços de letras** à esquerda e em cima (o título da coluna), e **o que os números fazem na
  tabela** — erro = encontrado − nominal, nominal crescente e "redondo", k constante, incerteza
  positiva. A posição na folha entra só como pista fraca.
- **Como saber se aprendeu** — três provas, da mais fácil para a mais difícil:
  1. certificados novos de laboratórios já vistos (pode ser só decorar);
  2. **laboratório nunca visto** (treina com 4, testa no 5º): é a prova que conta;
  3. escaneado lido por OCR (treino só com digital).
- Modelos treinados ficam em `modelos/` (fora do Git, ADR 0002).

## Consequências
- O primeiro modelo tirava 100 % em laboratório conhecido e só 76,7 % das palavras (54,2 % dos
  campos) em laboratório novo: **decorava mais do que entendia**. As pistas numéricas e de
  pedaços de letras subiram para **80,4 %** das palavras e **73,2 %** dos campos, sem mexer no teste.
  No escaneado por OCR: 99,1 % das palavras e 98,1 % dos campos (laboratórios já vistos).
- O que ainda falha em laboratório novo é estrutura que nenhum laboratório de treino tinha (ex.: uma
  coluna de índice, ou a leitura antes do padrão). A cura é **mais variedade no treino**: cada
  laboratório e tipo novo de certificado entra com gabarito e o modelo é medido de novo.
- Com 5 laboratórios fictícios o teste "laboratório novo" é duro; nos certificados reais (etapa 5)
  o acerto deve ser medido com o mesmo método.
