# LeitorCertificadosIA — regras do projeto

Projeto de **estudo e portfólio** (repositório **público**): machine learning que lê certificados de
calibração em PDF (digitais e escaneados), acha os dados e confere com o plano de calibração.
Nasceu do SistemaCalibracao, mas é **separado**: nada daqui entra no programa da empresa.

O padrão geral (idioma, Git, README, versão) está no `CLAUDE.md` do usuário; aqui fica só o que é
deste projeto.

## Regras
- **Nunca** versionar certificado real, foto de certificado real, nome real de laboratório da
  empresa, código real de instrumento ou modelo treinado com dados reais (ADR 0002). Reais só em
  `dados/` (fora do Git). O caminho da pasta real fica só na memória local do Claude.
- **De graça e local**: scikit-learn, OCR local; nenhuma IA paga, nada sai do computador (ADR 0001).
- O usuário quer **aprender**: explicar cada passo (o porquê), uma etapa por vez.
- Testes com certificados fictícios gerados pelo próprio projeto.
- README só mostruário (sem "como rodar"), no estilo dos outros repositórios.

## Roteiro (cada etapa = branch + PR; versão 0.MENOR = etapa)
0. Fundação — pasta, `.venv`, Git, repositório público, README, ADRs.
1. Gerador de certificados fictícios (vários "laboratórios"), digital e "escaneado", com gabarito.
2. Ler o PDF — texto direto (digital) e OCR (escaneado).
3. Machine learning (scikit-learn) — achar os campos; medir acerto com treino × teste.
4. Comparar com o plano — tolerância ± U, como o SistemaCalibracao.
5. Teste com os reais — só no PC do usuário; README mostra só os números.

## Certificados do usuário
Tem **PDFs digitais e escaneados** (resposta do usuário em 2026-11-10).

## Onde paramos
- Etapa 0 (fundação) juntada no PR #1.
- **Etapa 1 (2026-11-10, versão 0.1.0)**: `src/leitor_certificados/ficticio/` — 5 laboratórios
  inventados, PDF digital + escaneado + gabarito `.json` com caixas (ADR 0003). Lote:
  `python -m leitor_certificados.ficticio.gerar --pasta dados/ficticios --quantidade 200`
  (fora do Git). Exemplos e figuras do README: `scripts/exemplos_e_figuras.py`.
- **Etapa 2 (2026-11-11, 0.2.0, PR #3)**: `leitura/` — PDF digital (texto direto) e escaneado (OCR
  RapidOCR), `ler_pdf` escolhe por página (ADR 0004). OCR vira folha invertida sozinho
  (`Pagina.rotacao`; pistas: confiança média < 0,93 ou "CERTIFICADO" só na metade de baixo).
- **Etapa 3 (2026-11-11, 0.3.0, PR #4)**: `aprendizado/` — regressão logística (scikit-learn) diz o
  que cada palavra é; pistas = jeito do texto, vizinhos, pedaços de letras e aritmética da tabela
  (ADR 0005). Medida (`scripts/medir_modelo.py`): laboratório novo 80,4 % das palavras / 73,2 % dos
  campos; laboratório conhecido 100 %; OCR 99,1 %.
- **Etapa 4 (em andamento, branch `etapa-4-conferir-plano`, ainda sem PR)**: `conferencia/` — regra
  erro ± U (cópia da do DQ05), `PlanosDQ05` lê o banco só leitura, `extracao`, `conferir` (acha o
  código no cadastro; reatribui colunas pelo plano). `ficticio/plano.py` gera planos inventados.
  Medida (`scripts/medir_conferencia.py`, 1ª rodada): digital novo 30/30 pareceres; OCR 23/30 (1
  decisão errada, resto pendente); laboratório novo mal (muito "pendente"). A 2ª rodada (com as
  melhorias) **não terminou** — refazer. Falta: ADR 0006, README, versão 0.4.0, PR.
- **Banco do DQ05**: cópia em `dados/banco_dq05/release_1_2_0/calibracao.db` (Release privada
  `calibracao-v1.2.0-2026-11-10` de `jcesarmph-ui/programas-executaveis`; esquema v9). O
  `SistemaCalibracao/dados/calibracao.db` local é de 29/10 — não usar. Vale a U do **certificado**.
- **Certificados reais** (`dados/certificados_reais/`, 4: 1 digital Laftec + 3 escaneados, um
  invertido e um de outro laboratório de balanças com leituras 01/02/03). Pré-marcação do modelo:
  `scripts/pre_rotular_reais.py` → `dados/reais_marcacao/` (PNG + JSON, fora do Git). Achados: o
  Laftec traz colunas **"Erro Máximo"** e **"Critério de aceitação ±"** (o modelo as chama de
  incerteza) e há texto solto marcado por insegurança.
- **Próximos passos (o usuário disse "você faz tudo")**: (1) refazer a medida da etapa 4 e fechar o
  PR; (2) gerador de fictícios estilo Laftec (colunas Erro Máximo/Critério/veff, "Parâmetro") e
  rótulos novos `ponto.erro_maximo`/`ponto.criterio`; (3) limiar de certeza (palavra incerta →
  "outro"); (4) gabarito dos reais (corrigir o JSON da pré-marcação) e medir/treinar com eles
  (modelos reais só em `modelos/`, fora do Git); (5) tela estilo Google Lens com checks (memória
  `tela-estilo-lens-com-checks`); (6) etapa 5.
