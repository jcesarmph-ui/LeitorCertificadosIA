"""Gera um lote de certificados fictícios: para cada um, três arquivos.

- `cert_0001_digital.pdf`   — PDF com texto (como sai do sistema do laboratório);
- `cert_0001_escaneado.pdf` — o mesmo certificado, só imagem (como sai de um scanner);
- `cert_0001.json`          — o **gabarito**: as respostas certas e onde cada uma está na folha.

Cada certificado tem a sua semente (`<semente>-<número>`): gerar de novo dá exatamente o mesmo
lote, e um certificado pode ser refeito sozinho.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .dados import sortear_certificado
from .desenho import desenhar
from .escaneado import escanear


def gerar_um(pasta: Path, numero: int, semente: int = 2026) -> Path:
    """Gera os três arquivos de um certificado e devolve o caminho do gabarito."""
    pasta.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{semente}-{numero}")
    ident = f"cert_{numero:04d}"
    cert = sortear_certificado(rng, ident)
    digital = pasta / f"{ident}_digital.pdf"
    escaneado = pasta / f"{ident}_escaneado.pdf"
    campos = desenhar(cert, digital, rng)
    campos_escaneado, ajustes = escanear(digital, escaneado, rng, campos)
    gabarito = {
        "ficticio": True,
        "semente": f"{semente}-{numero}",
        "certificado": cert.para_dict(),
        "nome_laboratorio": cert.lab.nome,
        "digital": {"arquivo": digital.name, "campos": campos},
        "escaneado": {"arquivo": escaneado.name, "campos": campos_escaneado, **ajustes},
    }
    destino = pasta / f"{ident}.json"
    destino.write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def gerar_lote(pasta: Path, quantidade: int, semente: int = 2026) -> list[Path]:
    return [gerar_um(pasta, n, semente) for n in range(1, quantidade + 1)]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gera certificados de calibração fictícios.")
    parser.add_argument("--pasta", type=Path, default=Path("dados/ficticios"))
    parser.add_argument("--quantidade", type=int, default=200)
    parser.add_argument("--semente", type=int, default=2026)
    args = parser.parse_args(argv)
    gabaritos = gerar_lote(args.pasta, args.quantidade, args.semente)
    print(f"{len(gabaritos)} certificados fictícios em {args.pasta}")


if __name__ == "__main__":
    main()
