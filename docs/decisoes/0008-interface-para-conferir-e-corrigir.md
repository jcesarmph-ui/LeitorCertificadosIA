# 0008 — Interface: conferir, corrigir e reaprender pela tela

**Data:** 2026-11-12 · **Situação:** aceita

## Contexto
Até a etapa de aprendizado com o uso (ADR 0007), corrigir um certificado real era editar um
arquivo `.palavras.json` por script e conferir numa foto. Funciona para medir, mas não para usar
no dia a dia: o objetivo do programa é **abrir o certificado e ver na hora se ele bate com o
plano** (código, faixa e tolerância) e, quando o modelo errar, **corrigir ali mesmo** para que
ele aprenda.

## Decisão
- **Programa desktop em PySide6**, como os outros programas do autor (sem servidor, sem
  navegador), em camadas: `interface/servico.py` faz todo o fluxo sem tela (analisar, corrigir,
  digitar à mão, reconferir, aprender) e é testado sem janela; a janela só chama o serviço e
  desenha o resultado.
- **A folha é a tela principal**: o certificado aparece no tamanho de uma A4, com cada palavra
  numa caixa e um **check verde ou ✗ vermelho** em cada ponto conferido. Clicar num ponto abre um
  quadrinho com a conta (erro ± U × tolerância) e a certeza do modelo em cada número.
- **O que demora roda em segundo plano** (OCR, treino): a tela não trava, mostra uma faixa de
  "raio X" com brilhos descendo pela folha (inspirado no Google Lens) e o botão **Cancelar
  análise** volta ao certificado anterior. O OCR não tem como parar no meio, então o resultado
  atrasado é simplesmente descartado.
- **Corrigir pela tela, de três jeitos**:
  1. **Rótulo errado** (o modelo chamou o erro de incerteza): clicar na palavra, ou arrastar um
     retângulo sobre várias, e escolher o que ela é;
  2. **Texto lido errado** (o OCR leu "0,0l"): duplo clique e escrever o certo (`texto_certo`,
     usado também no treino);
  3. **Valor que o modelo não consegue ler** (código escrito a caneta): digitar à mão, gravado na
     chave `manual`; a conferência roda de novo na hora.

  Tudo fica no mesmo `.palavras.json` da ADR 0007, fora do Git. O botão **Aprender com as
  correções** retreina o modelo com os fictícios mais os reais corrigidos e confere de novo o
  certificado aberto.
- **Pouca certeza não vira parecer**: palavra com certeza abaixo de 0,5 (`LIMIAR_CERTEZA`) fica
  fora da conferência e marcada para revisar; a faixa diferente do plano só gera aviso amarelo
  (não muda o parecer).
- **Paleta própria deste programa** ("claro azulado", com as caixas da folha todas azuis),
  escolhida pelo autor entre quatro opções. Verde, vermelho e amarelo ficam reservados para o que
  significam (aprovado, reprovado, aviso).

## Consequências
- O ciclo "abrir → conferir → corrigir → aprender" agora acontece todo pela tela, sem script.
- A janela é testada em modo offscreen com certificados fictícios (pytest); as fotos do README
  são geradas do mesmo jeito, com dados 100 % fictícios.
- **Fica para depois** (pedido do autor): salvar um **registro de cada análise** (quem, quando,
  qual certificado, o que o modelo leu, o que foi corrigido, parecer, versão do programa e do
  modelo), para rastreabilidade. O formato será decidido antes de implementar.
