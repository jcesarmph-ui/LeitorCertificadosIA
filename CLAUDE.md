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
- **Paleta de cores própria deste programa** (pedido do usuário, 2026-11-12): a interface
  inteira pode fugir do tema escuro padrão do `CLAUDE.md` geral — vale **só aqui**; não
  "consertar" de volta para o padrão nem mudar o `CLAUDE.md` geral. A paleta fica em
  `interface/estilo.py` (`TEMAS`, `TEMA_ATUAL`) e `interface/paletas.py`. **Escolha do usuário
  (2026-11-12): tema "claro_azulado"** e caixas da folha todas azuis (paleta "E").

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
- **Etapa 4 fechada (PR #5, 0.4.0, ADR 0006)**; 2ª rodada de medida registrada no README.
- **Objetivo do leitor (usuário, 2026-11-12)**: ver o que tem no certificado e **comparar com o
  plano** — **código**, **faixa** e principalmente **tolerância** (pontos nominal/erro/incerteza).
  Medir o que importa nisso ("essenciais"); fabricante/laboratório/técnico são secundários.
  **Faixa** (decisão do usuário): `conferencia/faixa.py` compara mínimo e máximo e **só avisa em
  amarelo** (diferente ou não comparável); não muda o parecer. Plano "Máx. X / mín. Y" e escalas
  (durômetro) ficam como "não comparada".
- **Decisão do usuário (2026-11-12)**: não perseguir laboratório novo; o modelo **aprende com o
  uso** (reais corrigidos → retreino). Branch `etapa-5-aprendizado-por-correcao`:
  `aprendizado/correcoes.py` (peso 5 nos reais), `scripts/corrigir_reais.py` (corrige por
  número/faixa), `scripts/foto_revisao.py` (foto do que mudou), `scripts/medir_aprendizado.py`
  (deixa um real de fora). Propostas de correção dos 4 reais em `dados/correcoes/propor_*.py`
  (fora do Git; o usuário revisa). **Achado**: o carimbo "ESTE CERTIFICADO FOI ANALISADO" enganava
  a detecção de folha invertida (`leitura/ocr.py`, corrigido: só "CERTIFICADO DE" é título).
  Medida (essenciais: código, faixa, nominal, encontrado, erro, incerteza; média dos 4 reais
  deixados de fora): **só fictícios 70,2 % → +1 real 83,0 % → +2 89,2 % → +3 91,5 %**; "falsos"
  (palavra "outro" marcada como campo) 75 → 30. Cuidado ao contar: Laftec digital e escaneado são do
  mesmo laboratório (um ajuda o outro). Falta: usuário revisar scan1 (refeito, 110 mudanças), ADR
  0007, README, versão 0.5.0, PR.
- **Interface (PySide6, 2026-11-12)**: `interface/` (feita por um agente; commit 8299af8),
  `python -m leitor_certificados.interface`. Limiar de certeza 0,5 (`modelo.LIMIAR_CERTEZA`) na
  conferência. 2ª rodada de ajustes pedida pelo usuário (em andamento): escolher paleta (4 fotos;
  caixas sem verde/vermelho/amarelo, que têm significado), quadrinho ao clicar num ponto
  conferido (certeza, encontrado ± U, tolerância), legenda de cores, Ctrl+roda = zoom, check
  mais aparente, brilhos estilo Google Lens + varredura raio X, digitar valor à mão (código a
  caneta; chave `manual` no `.palavras.json`), cancelar análise, "Analisar outro".
- **Pedido para DEPOIS (usuário, 2026-11-12)**: **salvar e registrar cada análise** para
  transparência, governança e rastreabilidade (quem, quando, qual certificado, o que o modelo
  leu, o que foi corrigido/digitado, parecer, versão do programa e do modelo). Perguntar o
  formato antes de fazer.
- **Próximos passos**: (1) corrigir os reais e medir o ganho; (2) gerador estilo Laftec + rótulos
  `ponto.erro_maximo`/`ponto.criterio`; (3) limiar de certeza; (4) tela estilo Lens com checks
  (memória `tela-estilo-lens-com-checks`); (5) teste com os reais (etapa final, só os números).
