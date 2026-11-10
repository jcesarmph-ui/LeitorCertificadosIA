"""Primeiro teste: confere que o pacote abre e tem uma versão no formato MAIOR.MENOR.CORREÇÃO."""

import re

import leitor_certificados


def test_versao_no_formato_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", leitor_certificados.__version__)
