"""Etapa 4 — conferir o certificado com o plano de calibração.

- `plano.py`      — lê o plano do instrumento no banco do DQ05 (cópia, só leitura);
- `extracao.py`   — monta a tabela de pontos a partir do que o modelo achou na folha;
- `avaliacao.py`  — a regra: erro ± U cabe na tolerância?
- `conferir.py`   — junta tudo e devolve o parecer, ponto a ponto, com avisos.
"""
