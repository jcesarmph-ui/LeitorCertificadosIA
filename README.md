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
  <img src="https://img.shields.io/badge/versão-0.0.1_em_desenvolvimento-orange?style=flat-square" alt="Versão"/>
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

## 🛠️ Tecnologias

| Tecnologia | Aplicação no projeto |
|---|---|
| Python | Linguagem de todo o projeto. |
| scikit-learn | Modelo de machine learning (gratuito, roda no computador). |
| OCR local | Leitura dos certificados escaneados (definido na etapa de leitura). |
| pytest + ruff | Testes automáticos com certificados fictícios e padronização do código. |
| Git + GitHub | Uma branch e um pull request por etapa; decisões registradas em ADRs. |
| Claude Code | Desenvolvimento assistido por IA, com o autor definindo e aprovando cada etapa. |

Decisões de arquitetura: [`docs/decisoes/`](docs/decisoes/).

## 🗺️ Roteiro

- [x] Etapa 0 — Fundação (estrutura, versão, testes, decisões de arquitetura)
- [ ] Etapa 1 — Gerador de certificados fictícios (digital e "escaneado") com gabarito
- [ ] Etapa 2 — Leitura do PDF: texto direto e OCR
- [ ] Etapa 3 — Machine learning: encontrar os campos; acerto medido em treino × teste
- [ ] Etapa 4 — Conferência com o plano: erro ± U dentro da tolerância
- [ ] Etapa 5 — Teste com certificados reais (só os números de acerto aparecem aqui)

---

<p align="center">
  <b>Projeto de estudo de machine learning aplicado à metrologia: aprender, medir o acerto e mostrar
  a evolução — com dados 100% fictícios.</b>
</p>
