# Leitor de Certificados com IA

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white" alt="scikit-learn"/>
  <img src="https://img.shields.io/badge/Machine_Learning-8A2BE2?style=for-the-badge&logo=databricks&logoColor=white" alt="Machine Learning"/>
  <img src="https://img.shields.io/badge/OCR-555555?style=for-the-badge&logo=googledocs&logoColor=white" alt="OCR"/>
  <img src="https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" alt="pytest"/>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white" alt="Git"/>
  <img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/>
  <img src="https://img.shields.io/badge/Claude_Code-D97757?style=for-the-badge&logo=claude&logoColor=white" alt="Claude Code"/>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/área-metrologia_e_qualidade-blue?style=flat-square" alt="Área"/>
  <img src="https://img.shields.io/badge/tipo-machine_learning-purple?style=flat-square" alt="Tipo"/>
  <img src="https://img.shields.io/badge/dados-100%25_fictícios-brightgreen?style=flat-square" alt="Dados"/>
  <img src="https://img.shields.io/badge/custo-gratuito_e_local-success?style=flat-square" alt="Custo"/>
  <img src="https://img.shields.io/badge/versão-0.2.0_em_desenvolvimento-orange?style=flat-square" alt="Versão"/>
  <img src="https://img.shields.io/badge/idioma-pt--BR-green?style=flat-square" alt="Idioma"/>
</p>

<p align="center">
  Projeto de estudo de <b>machine learning</b>: um modelo que lê <b>certificados de calibração em
  PDF</b> — digitais ou escaneados —, encontra os dados importantes e confere se o instrumento está
  dentro da tolerância do plano de calibração, considerando a incerteza de medição.
</p>

<p align="center">
  <a href="#-visão-geral">Visão Geral</a> •
  <a href="#-como-vai-funcionar">Como vai funcionar</a> •
  <a href="#-dados-fictícios">Dados fictícios</a> •
  <a href="#-certificados-fictícios">Certificados fictícios</a> •
  <a href="#-leitura-do-pdf">Leitura do PDF</a> •
  <a href="#️-tecnologias">Tecnologias</a> •
  <a href="#️-roteiro">Roteiro</a>
</p>

---

## 📌 Visão Geral

Este projeto nasceu do [**Sistema de Gestão de Calibração**](https://github.com/jcesarmph-ui/SistemaCalibracao),
um aplicativo desktop em uso numa empresa. Lá, cada calibração é digitada à mão a partir do
certificado do laboratório. A pergunta deste projeto é: **dá para uma IA gratuita, rodando no
próprio computador, ler o certificado e conferir sozinha?**

É um projeto para **aprender e mostrar o aprendizado**: cada etapa mede o acerto do modelo e
registra o que melhorou — mesmo quando ele erra.

| ❌ Problema | 💡 Solução | ✅ Resultado esperado |
|---|---|---|
| Digitar cada ponto do certificado é demorado e sujeito a erro. | Modelo de **machine learning** que encontra nº do certificado, data, laboratório e os pontos medidos. | Dados extraídos automaticamente, com o **acerto medido**. |
| Certificados chegam em PDF digital **e** escaneado. | Dois caminhos: texto direto do PDF e **OCR** (ler a imagem). | Comparar o acerto de cada tipo. |
| Conferir a conformidade exige considerar a incerteza (U). | Regra de avaliação: `erro ± U` dentro da tolerância. | Parecer sugerido ponto a ponto. |
| IA paga e envio de documentos para a nuvem. | **scikit-learn** e OCR **locais e gratuitos**. | Nenhum dado sai do computador, custo zero. |

```mermaid
mindmap
  root((Leitor de Certificados))
    Dados de treino
      Certificados fictícios
      Vários laboratórios inventados
      Digital e escaneado
      Gabarito com as respostas
    Leitura
      Texto do PDF
      OCR
    Machine learning
      scikit-learn
      Treino e teste
      Acerto medido
    Conferência
      Tolerância
      Incerteza U
      Parecer sugerido
```

## 🧠 Como vai funcionar

```mermaid
flowchart LR
    PDF["📄 Certificado<br/>(PDF)"] --> T{"Tem texto?"}
    T -->|"Sim (digital)"| X["Texto direto"]
    T -->|"Não (escaneado)"| O["OCR"]
    X --> M["🤖 Modelo de ML<br/>acha os campos"]
    O --> M
    M --> C["📐 Confere com o plano<br/>erro ± U na tolerância?"]
    C --> R["✅ / ❌ por ponto"]
```

Um modelo de machine learning **aprende com exemplos que têm resposta**. Por isso o projeto começa
gerando certificados fictícios junto com o **gabarito** (o que o modelo deveria encontrar). Parte
deles serve para **treinar**; a outra parte, que o modelo nunca viu, serve para **testar** e medir
o acerto de verdade.

## 🔒 Dados fictícios

> [!IMPORTANT]
> Este repositório é público e **não contém nenhum certificado real**. Todos os certificados,
> laboratórios, instrumentos, números e pessoas que aparecem aqui são **inventados** pelo próprio
> projeto. Testes com certificados reais acontecem só no computador do autor, e aqui aparecem apenas
> os **números de acerto**.

## 🧾 Certificados fictícios

O primeiro passo foi construir um **gerador de certificados inventados**: o modelo só aprende com
exemplos que têm a resposta certa, e certificados reais não podem aparecer aqui. Cada certificado
gerado sai em **três arquivos**: o PDF **digital**, o mesmo certificado **"escaneado"** e o
**gabarito**.

**Cinco laboratórios inventados**, cada um com o seu jeito de montar a folha — para o modelo
aprender o que cada informação **é**, e não decorar onde ela fica:

<p align="center">
  <img src="docs/figuras/laboratorios.png" alt="Topo de um certificado fictício de cada um dos cinco laboratórios inventados" width="100%"/>
</p>

| O que muda de um laboratório para outro | Exemplos |
|---|---|
| Nome das informações | "Data da calibração", "Calibrado em", "DATA CALIBRACAO", "Calibration date" |
| Nome e ordem das colunas | "Valor indicado", "VI", "LEITURA", "Medido" — e a leitura às vezes vem antes do padrão |
| Formato da data | 09/03/2026 · 9 de março de 2026 · 09.03.2026 · 2026-03-09 · 09/mar/2026 |
| Números | vírgula ou ponto decimal; erro com ou sem "+"; fator k na tabela ou só na observação |
| Aparência | três fontes, três cabeçalhos, informações em lista ou em quadro, posição levemente sorteada |

**Digital × escaneado.** Muitos certificados chegam escaneados: são só uma foto da folha, sem
texto dentro do PDF. O gerador imita um scanner — folha um pouco torta, ruído do papel, desfoque e
compressão JPEG — para treinar e medir também a leitura por OCR:

<p align="center">
  <img src="docs/figuras/digital_x_escaneado.png" alt="O mesmo certificado fictício na versão digital e na versão escaneada" width="100%"/>
</p>

**O gabarito.** Para cada informação importante, o gabarito guarda **o valor certo e a caixa
onde ele está na folha** — também na versão torta. É com isso que o modelo vai ser ensinado e
corrigido:

<p align="center">
  <img src="docs/figuras/gabarito.png" alt="Certificado escaneado com as caixas do gabarito coloridas por tipo de informação" width="70%"/>
</p>

<details>
<summary><b>Como o gerador garante que o gabarito está certo</b></summary>

- Testes automáticos abrem cada PDF digital e conferem que o texto **dentro de cada caixa** é
  exatamente a resposta anotada.
- No escaneado, conferem que o PDF **não tem texto nenhum** (só imagem) e que dentro das caixas
  giradas há tinta — ou seja, elas acompanharam o giro da folha.
- Pontos coerentes: erro = encontrado − nominal; o primeiro e o último ponto são o começo e o fim
  da faixa; os do meio são valores "redondos", como num certificado de verdade.
- Cada certificado tem a sua **semente**: gerar de novo produz exatamente o mesmo arquivo, para
  repetir treinos e comparar resultados de forma justa.
- Exemplos prontos (um de cada laboratório) em [`exemplos/`](exemplos/).

</details>

## 👁️ Leitura do PDF

A segunda etapa transforma qualquer PDF numa **lista de palavras com posição** (a mesma medida do
gabarito), igual nos dois casos — assim o machine learning da próxima etapa não precisa saber de
onde a palavra veio. O programa escolhe o caminho **página por página**:

| Caminho | Como lê | Acerto* | Tempo por certificado |
|---|---|---|---|
| 📄 **Digital** | Texto e posição direto de dentro do PDF | **100 %** (1525 de 1525) | 0,01 s |
| 🖼️ **Escaneado** | **OCR** local (RapidOCR): acha as linhas na imagem e lê as letras | **98,1 %** (1496 de 1525) | cerca de 5 s |

<sub>*Respostas do gabarito lidas sem nenhum erro, em 30 certificados fictícios.</sub>

No OCR cada palavra guarda a **confiança** (verde = certeza alta, amarelo = dúvida, vermelho = pouca
certeza). Os erros que sobram são quase todos números pequenos da tabela (a vírgula lida como
apóstrofo) e o nome do laboratório grudado no endereço:

<p align="center">
  <img src="docs/figuras/leitura_ocr.png" alt="Certificado fictício escaneado com o que o OCR leu, colorido pela confiança" width="70%"/>
</p>

> [!NOTE]
> Os fictícios são mais limpos que os escaneados de verdade: num teste com um escaneado real, a
> confiança média do OCR ficou bem abaixo da dos fictícios. Por isso o gerador imita um scanner
> mais ruim (150 dpi, mais ruído) e a etapa 5 vai mostrar o acerto real, sem esconder a diferença.

## 🛠️ Tecnologias

| Tecnologia | Aplicação no projeto |
|---|---|
| Python | Linguagem de todo o projeto. |
| scikit-learn | Modelo de machine learning (gratuito, roda no computador). |
| reportlab | Escreve os PDFs digitais dos certificados fictícios. |
| pypdfium2 | Transforma o PDF em imagem (para o "escaneado") e lê o texto do PDF. |
| Pillow | Imita o scanner: giro, ruído, desfoque e compressão JPEG. |
| RapidOCR (ONNX) | OCR local e gratuito: lê os certificados escaneados, palavra por palavra, com a confiança de cada uma. |
| pytest + ruff | Testes automáticos com certificados fictícios e padronização do código. |
| Git + GitHub | Uma branch e um pull request por etapa; decisões registradas em ADRs. |
| Claude Code | Desenvolvimento assistido por IA, com o autor definindo e aprovando cada etapa. |

Decisões de arquitetura: [`docs/decisoes/`](docs/decisoes/).

## 🗺️ Roteiro

- [x] Etapa 0 — Fundação (estrutura, versão, testes, decisões de arquitetura)
- [x] Etapa 1 — Gerador de certificados fictícios (5 laboratórios, digital e "escaneado") com gabarito anotado
- [x] Etapa 2 — Leitura do PDF: texto direto e OCR (palavras com posição e confiança)
- [ ] Etapa 3 — Machine learning: encontrar os campos; acerto medido em treino × teste
- [ ] Etapa 4 — Conferência com o plano: erro ± U dentro da tolerância
- [ ] Etapa 5 — Teste com certificados reais (só os números de acerto aparecem aqui)

---

<p align="center">
  <b>Projeto de estudo de machine learning aplicado à metrologia: aprender, medir o acerto e mostrar
  a evolução — com dados 100% fictícios.</b>
</p>
