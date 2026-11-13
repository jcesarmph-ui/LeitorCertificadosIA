# 0006 — Conferência com o plano: parecer só quando há certeza

**Data:** 2026-11-12 · **Situação:** aceita

## Contexto
Depois de ler os campos (etapa 3), o programa precisa dizer se o instrumento **passou**: o erro de
cada ponto, somado à incerteza de medição (U), cabe na tolerância do plano de calibração? O plano
vem do banco do SistemaCalibracao (DQ05), que não pode ser alterado.

## Decisão
- **Mesma regra do DQ05** (`erro ± U` contra a tolerância; vale a U do **certificado**), copiada para
  `conferencia/avaliacao.py`. O programa não inventa regra própria.
- **Plano lido só em leitura** (`PlanosDQ05`, SQLite `mode=ro`). Dados reais ficam fora do Git
  (ADR 0002); os testes usam planos inventados (`ficticio/plano.py`).
- **O código do instrumento é procurado no cadastro** a partir do texto do certificado, e as colunas
  da tabela são reatribuídas usando o plano (ex.: qual coluna é o erro, qual é a incerteza).
- **Na dúvida, "pendente"**: se faltar ponto, código ou coluna, o parecer não é dado. Um "pendente"
  custa uma conferência manual; uma decisão errada custa confiança no programa.

## Consequências
Medida (`scripts/medir_conferencia.py`, 150 certificados fictícios, PDF → leitura → modelo → plano):

| Prova | Pareceres certos | Pendentes | Decisão errada |
|---|---|---|---|
| Digital, certificados novos | 30/30 | 0 | 0 |
| Escaneado (OCR) | 23/30 | 6 | 1 |
| Laboratório nunca visto (média de 5) | varia de 0 % a 98 % | maioria nos piores | 0 |

- Em laboratório novo, três dos cinco ficaram quase todos "pendentes": o programa **não chuta**.
- Houve **1 decisão errada** no escaneado, sem aviso — ponto a vigiar (ver "Aprendizado contínuo").
- Não se tentará deixar o modelo perfeito para qualquer laboratório de antemão. O caminho é o
  **aprendizado com o uso**: o usuário sobe certificados reais, corrige o que foi lido errado e o
  modelo é retreinado com essas correções (próxima etapa).
