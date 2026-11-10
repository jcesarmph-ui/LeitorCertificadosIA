# 0002 — Repositório público só com certificados fictícios

**Data:** 2026-11-10 · **Situação:** aceita

## Contexto
O repositório é **público** (portfólio). Os certificados reais de calibração são documentos da
empresa: laboratórios, instrumentos, valores e pessoas reais. Eles **não podem** aparecer no GitHub.

## Decisão
- O projeto tem um **gerador de certificados fictícios** (laboratórios, instrumentos, números e
  pessoas inventados), em versão digital e "escaneada", cada um com o **gabarito** (respostas
  certas). É com eles que o modelo é treinado e os testes automáticos rodam.
- Os certificados reais ficam em `dados/` (fora do Git, pelo `.gitignore`) e só são usados no
  computador do autor, para medir o acerto no mundo real. O README mostra **apenas os números**
  desse teste (ex.: % de campos certos), nunca o conteúdo.
- O `.gitignore` bloqueia qualquer PDF/imagem fora de `exemplos/` e `docs/figuras/`, e qualquer
  modelo treinado (`modelos/`, `*.joblib`), porque um modelo treinado com dados reais pode "guardar"
  pedaços deles.

## Consequências
- Qualquer pessoa vê o projeto funcionando com dados fictícios; nada da empresa fica exposto.
- O modelo que vai para a apresentação é sempre treinado só com fictícios.
