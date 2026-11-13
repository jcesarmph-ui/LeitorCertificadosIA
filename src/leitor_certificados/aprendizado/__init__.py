"""Etapa 3 — machine learning: o modelo aprende, palavra por palavra, **o que cada palavra é**.

Fluxo:
1. `rotulos.py`   — com o gabarito, cada palavra lida ganha a sua resposta certa (ou "outro");
2. `atributos.py` — cada palavra vira uma lista de pistas (como é escrita, onde está, o que há
   ao lado e em cima dela);
3. `modelo.py`    — o scikit-learn aprende a ligar as pistas à resposta e depois é medido em
   certificados que nunca viu.
"""
