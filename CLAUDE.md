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
