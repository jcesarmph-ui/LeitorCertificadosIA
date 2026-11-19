"""Assinatura digital do PDF aprovado (lacre contra alteração).

Depois do carimbo, o PDF é **assinado digitalmente**: uma "impressão digital" (hash) de todo o
arquivo é trancada com a chave privada e gravada dentro do próprio PDF. O Adobe Reader confere
sozinho: se alguém mexer no PDF depois, ele avisa "o documento foi alterado".

O certificado é **próprio** (autoassinado, gratuito), criado uma vez na pasta de dados: prova
que o PDF não foi mexido, mas não tem validade legal fora da empresa (o Adobe mostra
"identidade desconhecida"). Para validade legal seria preciso um certificado ICP-Brasil.

A chave fica **fora do Git** (pasta de dados), nunca no repositório.
"""

from __future__ import annotations

import datetime
from pathlib import Path

ARQUIVO = "certificado_assinatura.pfx"
NOME_PADRAO = "Conferência de certificados de calibração"


def criar_certificado(destino: Path, nome: str = NOME_PADRAO, anos: int = 20) -> Path:
    """Cria a chave e o certificado autoassinado (arquivo .pfx), só se ainda não existe."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    destino = Path(destino)
    if destino.exists():
        return destino
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeito = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    agora = datetime.datetime.now(datetime.UTC)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(sujeito).issuer_name(sujeito)  # autoassinado: ele mesmo é o emissor
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=1))
        .not_valid_after(agora + datetime.timedelta(days=365 * anos))
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=True, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .sign(chave, hashes.SHA256()))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(pkcs12.serialize_key_and_certificates(
        nome.encode(), chave, certificado, None, serialization.NoEncryption()))
    return destino


def assinar_pdf(caminho: Path | str, certificado: Path, motivo: str,
                nome: str = NOME_PADRAO) -> Path:
    """Assina o PDF no lugar (o arquivo ganha a assinatura no fim, sem mudar o que se vê)."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    caminho = Path(caminho)
    criar_certificado(certificado, nome)
    assinante = signers.SimpleSigner.load_pkcs12(str(certificado), passphrase=None)
    with caminho.open("rb") as entrada:
        escritor = IncrementalPdfFileWriter(entrada, strict=False)
        assinado = signers.sign_pdf(
            escritor,
            signers.PdfSignatureMetadata(field_name="Conferencia", reason=motivo, name=nome),
            signer=assinante)
        conteudo = assinado.getvalue()
    caminho.write_bytes(conteudo)
    return caminho


def conferir_assinatura(caminho: Path | str) -> dict:
    """O que o Adobe diria: se o PDF está intacto desde a assinatura (para testes e tela)."""
    import logging

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    with Path(caminho).open("rb") as entrada:
        leitor = PdfFileReader(entrada, strict=False)
        if not leitor.embedded_signatures:
            return {"assinado": False, "intacto": False}
        assinatura = leitor.embedded_signatures[0]
        # certificado próprio = "não confiável" por natureza: não encher a tela com esse aviso
        logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
        estado = validate_pdf_signature(assinatura, ValidationContext(allow_fetching=False))
        return {"assinado": True, "intacto": bool(estado.intact and estado.valid),
                "documento_inteiro": estado.coverage.name == "ENTIRE_FILE",
                "confiavel": bool(estado.trusted),
                "assinante": assinatura.signer_cert.subject.human_friendly}
