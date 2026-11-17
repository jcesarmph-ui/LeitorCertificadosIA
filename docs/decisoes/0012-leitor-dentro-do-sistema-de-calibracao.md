# 0012 — O leitor vira uma peça do sistema de calibração

**Data:** 2026-11-17 · **Situação:** aceita

## Contexto
O leitor nasceu como projeto de estudo, separado do programa da empresa. Ficou bom o bastante
para o uso: quem decide é sempre a pessoa (Aprovar/Rejeitar), e ele melhora com as correções.
O usuário decidiu que ele **não vai para a rede sozinho**: entra como uma função do sistema de
calibração, que já tem o `.exe`, a pasta na rede, a trava de edição e o backup diário.

O que mais toma tempo hoje é digitar a calibração ponto por ponto e depois subir o PDF.

## Decisão
- O leitor **continua um projeto separado** (código, testes e GitHub próprios) e o sistema de
  calibração o **instala e usa por dentro**, como uma biblioteca. Melhorias do leitor são feitas
  aqui; o encaixe (botão, tela, gravar no banco, `.exe`) é feito no sistema de calibração.
- O leitor entrega uma **saída em tipos simples** (`saida.py`, vira JSON sem esforço) quando a
  pessoa registra e decide: cada ponto conferido com o **id da linha do plano** (`pontos_plano`)
  e os valores (encontrado, erro, incerteza, resultado), a data da calibração, os padrões, a
  decisão (quem, RE, data), as pendências (ignoradas ou não) e o **PDF carimbado**.
- A janela do leitor avisa o sistema pelo sinal `Janela.registrado(dict)`.
- No sistema de calibração: os pontos entram **sozinhos** na calibração, a pessoa confere e salva
  (o leitor nunca grava no banco do sistema); o botão "Subir PDF" fica travado, porque o PDF
  carimbado já veio do leitor.
- **Um só aprendizado para todos**: o modelo e as correções ficam na pasta de dados da rede
  (`Pastas` aponta para lá); toda correção registrada ensina o mesmo modelo.
- Os planos são lidos do **banco do próprio sistema** (só leitura), não de uma cópia.
- `VERSAO` da saída muda se o formato mudar, para o sistema saber o que está lendo.

## Consequências
- Acaba a regra antiga "nada daqui entra no programa da empresa" (era cautela enquanto o leitor
  era só estudo). Continua valendo: nada da empresa no GitHub público.
- O registro separado do leitor passa a ser o histórico das análises; o registro oficial é a
  calibração salva no sistema.
- Trava de edição e backup: usam os do sistema de calibração.
