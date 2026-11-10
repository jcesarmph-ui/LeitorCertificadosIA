"""Gerador de certificados de calibração FICTÍCIOS, com o gabarito de cada um.

Por que existe: um modelo de machine learning aprende com exemplos que já têm a resposta certa.
Certificados reais não podem ir para o GitHub (ADR 0002), então o projeto inventa os seus:
- `dados.py`       sorteia o conteúdo (instrumento, pontos, datas, pessoas — tudo inventado);
- `laboratorios.py` define laboratórios inventados, cada um com o seu "jeito" de montar a folha;
- `desenho.py`     escreve o PDF digital e anota onde ficou cada informação (o gabarito);
- `escaneado.py`   transforma o PDF em imagem "escaneada" (torta, com ruído, sem texto);
- `gerar.py`       gera um lote: PDF digital + PDF escaneado + gabarito (.json) por certificado.
"""
