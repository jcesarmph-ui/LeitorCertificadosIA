"""Interface gráfica (PySide6): abrir um certificado, ver o que o modelo achou, conferir com o
plano, corrigir e fazer o modelo aprender com o uso.

Camadas: `janela.py`/`folha.py` (tela) → `servico.py` (regras do fluxo, sem Qt) → módulos de
leitura, aprendizado e conferência. A tela nunca decide nada sozinha.
"""
