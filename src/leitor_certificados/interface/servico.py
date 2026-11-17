"""O fluxo do programa, sem nada de tela: analisar, corrigir, digitar à mão e aprender.

Tudo aqui pode ser testado sem abrir janela. A interface só chama estas funções (em segundo
plano, porque o OCR e o treino demoram) e desenha o que elas devolvem.

Onde ficam as coisas (todas FORA do Git — ADR 0002; `dados/` e `modelos/` estão no .gitignore):
- `dados/rascunhos/<nome>.palavras.json` — as correções da análise aberta (e os valores
  digitados, na chave `manual`). Só valem para a tela até a pessoa clicar em "Registrar";
- `dados/registro/registro.db` — o registro das análises (etapa 10, ADR 0012): cada registro
  guarda a folha corrigida, e é ela que ensina o modelo;
- `dados/reais_marcacao/<nome>.palavras.json` — as correções feitas antes do registro (etapas
  5 a 9); continuam ensinando, a não ser que um registro do mesmo certificado as substitua;
- `dados/ficticios/` — certificados inventados usados no treino base;
- `dados/banco_dq05/release_1_2_0/calibracao.db` — cópia do banco dos planos (só leitura);
- `modelos/modelo_atual.joblib` — o modelo treinado.
"""

from __future__ import annotations

import dataclasses
import getpass
import hashlib
import json
import os
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from .. import __version__
from ..aprendizado import modelo as ml
from ..aprendizado.correcoes import marcacao_de_dados, treinar_com_correcoes
from ..aprendizado.rotulos import rotular
from ..conferencia.avaliacao import Avaliacao, Resultado, erro_com_incerteza
from ..conferencia.conferir import Conferencia, PontoConferido, conferir
from ..conferencia.criterio import SituacaoCriterio, descrever_criterio
from ..conferencia.extracao import CertificadoLido, montar_certificado
from ..conferencia.padroes import SituacaoPadrao, data_br
from ..conferencia.plano import PlanosDQ05
from ..ficticio.gerar import gabarito_atual
from ..leitura import Pagina
from ..leitura.ler import ler_pdf
from ..registro import RegistroAnalises

RAIZ = Path(__file__).resolve().parents[3]

# Os rótulos que o modelo conhece, com o nome que a pessoa entende na lista de correção.
ROTULOS: dict[str, str] = {
    "outro": "Outro (não é dado)",
    "codigo": "Código do instrumento",
    "tipo": "Tipo de instrumento",
    "fabricante": "Fabricante",
    "serie": "Número de série",
    "faixa": "Faixa de utilização",
    "resolucao": "Resolução",
    "numero_certificado": "Número do certificado",
    "data_calibracao": "Data da calibração",
    "data_emissao": "Data de emissão",
    "cliente": "Cliente",
    "laboratorio": "Laboratório",
    "temperatura": "Temperatura",
    "umidade": "Umidade",
    "tecnico": "Técnico",
    "ponto.nominal": "Ponto: valor nominal",
    "ponto.encontrado": "Ponto: valor encontrado",
    "ponto.erro": "Ponto: erro",
    "ponto.incerteza": "Ponto: incerteza (U)",
    "ponto.k": "Ponto: fator k",
    "ponto.erro_maximo": "Ponto: erro máximo",
    "ponto.criterio": "Ponto: critério de aceitação",
    "padrao.codigo": "Padrão: código (ou nº do certificado)",
    "padrao.validade": "Padrão: validade",
}

# O que dá para digitar à mão quando o modelo não consegue ler (ex.: código escrito a caneta).
CAMPOS_MANUAIS: dict[str, str] = {"codigo": "Código do instrumento", "faixa": "Faixa",
                                  "data_calibracao": "Data da calibração"}


@dataclass
class Pastas:
    """Onde o programa lê e grava. Nos testes aponta para uma pasta temporária."""

    marcacao: Path = RAIZ / "dados" / "reais_marcacao"
    ficticios: Path = RAIZ / "dados" / "ficticios"
    banco: Path = RAIZ / "dados" / "banco_dq05" / "release_1_2_0" / "calibracao.db"
    modelo: Path = RAIZ / "modelos" / "modelo_atual.joblib"
    quantidade_ficticios: int = 150  # tantos certificados inventados no treino
    # ao lado da pasta de marcação, se não for dito outro lugar (nos testes, tudo na temporária)
    rascunhos: Path | None = None
    registro: Path | None = None

    def __post_init__(self) -> None:
        self.rascunhos = self.rascunhos or self.marcacao.parent / "rascunhos"
        self.registro = self.registro or self.marcacao.parent / "registro" / "registro.db"


@dataclass
class Analise:
    """Tudo o que se sabe de um certificado aberto."""

    caminho: Path
    pagina: Pagina
    imagem: Image.Image  # a folha em pé (já virada, se o scanner a pegou de cabeça para baixo)
    previsoes: list[tuple[str, float]]  # o palpite do modelo: (rótulo, certeza) por palavra
    rotulos: list[str]  # o que a tela mostra: a correção da pessoa, quando existe
    corrigidas: set[int] = field(default_factory=set)
    certificado: CertificadoLido | None = None
    conferencia: Conferencia | None = None
    campos: dict[str, str] = field(default_factory=dict)  # o que o modelo leu (faixa, tipo…)
    manual: dict[str, str] = field(default_factory=dict)  # valores digitados à mão
    # texto corrigido à mão (o OCR leu errado): {índice da palavra: o que está escrito}
    textos_certos: dict[int, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)  # problemas da análise (banco ausente…)

    def texto(self, i: int) -> str:
        """O texto que vale para a palavra: o corrigido, se houver; senão o que foi lido."""
        return self.textos_certos.get(i, self.pagina.palavras[i].texto)

    def pagina_corrigida(self) -> Pagina:
        """A página com os textos corrigidos no lugar dos lidos (para conferir de novo)."""
        if not self.textos_certos:
            return self.pagina
        palavras = [dataclasses.replace(p, texto=self.textos_certos[i])
                    if i in self.textos_certos else p
                    for i, p in enumerate(self.pagina.palavras)]
        return Pagina(self.pagina.origem, palavras, self.pagina.rotacao)

    def certeza(self, i: int) -> float:
        return 1.0 if i in self.corrigidas else self.previsoes[i][1]

    def revisar(self, i: int) -> bool:
        """Palavra que o modelo acha que é um campo, mas com pouca certeza (< limiar): a
        conferência a ignora e a tela pede para a pessoa revisar."""
        return (self.rotulos[i] != "outro" and i not in self.corrigidas
                and self.previsoes[i][1] < ml.LIMIAR_CERTEZA)


Progresso = Callable[[str], None]


def _nada(_: str) -> None:
    pass


# ---------------------------------------------------------------- folha (imagem)

def renderizar_folha(caminho: Path | str, rotacao: int = 0, escala: float = 2.0) -> Image.Image:
    """A primeira página como imagem. Com `rotacao=180` a imagem é virada para ficar em pé: as
    caixas do OCR estão nesse quadro (o OCR leu a folha já virada), então imagem e caixas só
    combinam se a imagem for virada também."""
    documento = pdfium.PdfDocument(str(caminho))
    try:
        imagem = documento[0].render(scale=escala).to_pil().convert("RGB")
    finally:
        documento.close()
    return imagem.rotate(180) if rotacao == 180 else imagem


# ---------------------------------------------------------------- correções (JSON)

def arquivo_de_correcoes(pastas: Pastas, certificado: Path) -> Path:
    """O rascunho das correções da análise aberta (ainda não registrado)."""
    return pastas.rascunhos / f"{Path(certificado).stem}.palavras.json"


def _ensina(dados: dict) -> bool:
    """A folha tem alguma correção de rótulo ou de texto? (só o digitado à mão não ensina)"""
    return any(i["certo"] != i["rotulo"] or i.get("texto_certo")
               for i in dados.get("palavras", []))


def correcoes_oficiais(pastas: Pastas, so_as_que_ensinam: bool = True) -> dict[str, dict]:
    """{nome do certificado: folha corrigida} — o que ensina o modelo: as correções antigas
    (`reais_marcacao`, de antes do registro) e, por cima, as dos registros ativos. Um registro
    na Lixeira não conta, e então a correção antiga do mesmo certificado (se houver) volta."""
    oficiais: dict[str, dict] = {}
    if pastas.marcacao.exists():
        for arquivo in sorted(pastas.marcacao.glob("*.palavras.json")):
            chave = arquivo.name.removesuffix(".palavras.json")
            oficiais[chave] = json.loads(arquivo.read_text(encoding="utf-8"))
    for chave, marcacao in RegistroAnalises(pastas.registro).vigentes().items():
        if marcacao:
            oficiais[chave] = marcacao
        else:
            oficiais.pop(chave, None)  # o registro mais novo desfez todas as correções
    if so_as_que_ensinam:
        oficiais = {k: v for k, v in oficiais.items() if _ensina(v)}
    return oficiais


def assinatura_das_correcoes(oficiais: dict[str, dict]) -> str:
    """Uma "impressão digital" do que ensina o modelo: muda se qualquer correção mudar."""
    texto = json.dumps(oficiais, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _lido_confere(itens: list[dict], pagina: Pagina) -> bool:
    """O JSON guardado é desta mesma leitura? (mesmo número de palavras e mesmos textos)"""
    return len(itens) == len(pagina.palavras) and all(
        i["texto"] == p.texto for i, p in zip(itens, pagina.palavras, strict=True))


def _ler_arquivo(pastas: Pastas, caminho: Path) -> dict:
    """As correções que valem para a tela: o rascunho, se a pessoa já mexeu nesta análise;
    senão as oficiais (registradas ou antigas)."""
    arquivo = arquivo_de_correcoes(pastas, caminho)
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    return correcoes_oficiais(pastas, so_as_que_ensinam=False).get(Path(caminho).stem, {})


def _correcoes_existentes(dados: dict, pagina: Pagina) -> dict[int, str]:
    """{índice da palavra: rótulo corrigido} — só o que a pessoa de fato mudou."""
    itens = dados.get("palavras", [])
    if not itens or not _lido_confere(itens, pagina):
        return {}
    return {i["i"]: i["certo"] for i in itens if i["certo"] != i["rotulo"]}


def _itens_atuais(dados: dict, analise: Analise) -> list[dict]:
    """As palavras do arquivo, prontas para mudar. Se o arquivo não existe ou é de outra
    leitura, refaz a lista a partir da análise (o `certo` começa igual ao palpite), levando junto
    as correções cujo texto continua igual — a mesma regra do `pre_rotular_reais.py`."""
    antigos = {i["i"]: i for i in dados.get("palavras", [])}
    if antigos and _lido_confere(list(antigos.values()), analise.pagina):
        return list(antigos.values())
    itens = [
        {"i": i, "texto": p.texto, "caixa": list(p.caixa), "confianca": p.confianca,
         "rotulo": r, "certeza": round(c, 3), "certo": r}
        for i, (p, (r, c)) in enumerate(
            zip(analise.pagina.palavras, analise.previsoes, strict=True))
    ]
    for item in itens:
        antigo = antigos.get(item["i"])
        if antigo and antigo["texto"] == item["texto"]:
            if antigo["certo"] != antigo["rotulo"]:
                item["certo"] = antigo["certo"]
            if antigo.get("texto_certo"):
                item["texto_certo"] = antigo["texto_certo"]
        if item["i"] in analise.textos_certos:
            item["texto_certo"] = analise.textos_certos[item["i"]]
    return itens


def _textos_existentes(dados: dict, pagina: Pagina) -> dict[int, str]:
    """{índice: texto corrigido à mão} — só se o arquivo é desta mesma leitura."""
    itens = dados.get("palavras", [])
    if not itens or not _lido_confere(itens, pagina):
        return {}
    return {i["i"]: i["texto_certo"] for i in itens if i.get("texto_certo")}


def gravar_texto(pastas: Pastas, analise: Analise, indice: int, texto: str) -> bool:
    """Grava o texto que realmente está escrito na palavra `indice` (o OCR leu errado), na chave
    `texto_certo` do `.palavras.json`; o `texto` continua sendo o que o OCR leu. Texto vazio ou
    igual ao lido apaga a correção. Devolve True se ficou uma correção gravada."""
    dados = _ler_arquivo(pastas, analise.caminho)
    itens = _itens_atuais(dados, analise)
    texto = texto.strip()
    if texto and texto != itens[indice]["texto"]:
        itens[indice]["texto_certo"] = texto
        analise.textos_certos[indice] = texto
    else:
        itens[indice].pop("texto_certo", None)
        analise.textos_certos.pop(indice, None)
    _gravar(pastas, analise, itens, dados.get("manual", {}))
    return indice in analise.textos_certos


def _gravar(pastas: Pastas, analise: Analise, itens: list[dict], manual: dict) -> None:
    conteudo = {"origem": analise.pagina.origem, "rotacao": analise.pagina.rotacao,
                "palavras": itens}
    if manual:
        conteudo["manual"] = manual
    pastas.rascunhos.mkdir(parents=True, exist_ok=True)
    arquivo_de_correcoes(pastas, analise.caminho).write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=1), encoding="utf-8")


def gravar_correcao(pastas: Pastas, analise: Analise, indices: list[int], rotulo: str) -> int:
    """Grava `rotulo` como o certo para as palavras `indices` e devolve quantas mudaram.

    Cria o `.palavras.json` se não existir. Nada do que já foi corrigido (nem o que foi digitado
    à mão) se perde: só o `certo` das palavras indicadas muda."""
    if rotulo not in ROTULOS:
        raise ValueError(f"rótulo desconhecido: {rotulo}")
    dados = _ler_arquivo(pastas, analise.caminho)
    itens = _itens_atuais(dados, analise)
    mudaram = 0
    for i in indices:
        if itens[i]["certo"] != rotulo:
            itens[i]["certo"] = rotulo
            mudaram += 1
    _gravar(pastas, analise, itens, dados.get("manual", {}))
    for item in itens:  # a tela passa a mostrar o corrigido
        if item["certo"] != item["rotulo"]:
            analise.corrigidas.add(item["i"])
            analise.rotulos[item["i"]] = item["certo"]
        else:
            analise.corrigidas.discard(item["i"])
            analise.rotulos[item["i"]] = analise.previsoes[item["i"]][0]
    return mudaram


def gravar_manual(pastas: Pastas, analise: Analise, campo: str, valor: str) -> None:
    """Guarda um valor digitado à mão (chave `manual` do `.palavras.json`). Valor vazio apaga.
    Não entra no treino: serve só para a conferência deste certificado."""
    if campo not in CAMPOS_MANUAIS and campo != "padroes_calibrados":
        raise ValueError(f"campo que não se digita à mão: {campo}")
    dados = _ler_arquivo(pastas, analise.caminho)
    manual = dict(dados.get("manual", {}))
    valor = valor.strip()
    if valor:
        manual[campo] = valor
    else:
        manual.pop(campo, None)
    _gravar(pastas, analise, _itens_atuais(dados, analise), manual)
    analise.manual = manual


# ---------------------------------------------------------------- modelo

class Servico:
    """Guarda o modelo em uso e faz o trabalho pesado. Os métodos lentos rodam em segundo plano."""

    def __init__(self, pastas: Pastas | None = None):
        self.pastas = pastas or Pastas()
        self.modelo = None
        self._ficticios: tuple[list[Pagina], list[list[str]]] | None = None

    # -- treino ---------------------------------------------------------------------------
    def _carregar_ficticios(self, progresso: Progresso) -> tuple[list[Pagina], list[list[str]]]:
        """Lê os certificados inventados (gera os que faltam ou estão velhos). Fica em memória
        para os próximos treinos — ler 150 PDFs é a parte lenta."""
        if self._ficticios is None:
            paginas, rotulos = [], []
            total = self.pastas.quantidade_ficticios
            for n in range(1, total + 1):
                if n % 10 == 1:
                    progresso(f"Preparando certificados de treino ({n} de {total})")
                # gera os que faltam e refaz os de um gerador antigo (laboratório novo etc.)
                gabarito = gabarito_atual(self.pastas.ficticios, n)
                gab = json.loads(gabarito.read_text(encoding="utf-8"))
                pagina = ler_pdf(self.pastas.ficticios / gab["digital"]["arquivo"])[0]
                paginas.append(pagina)
                rotulos.append(rotular(pagina, gab["digital"]["campos"]))
            self._ficticios = (paginas, rotulos)
        return self._ficticios

    def aprender(self, progresso: Progresso = _nada) -> int:
        """Treina com fictícios + reais corrigidos (peso 5 nos reais), salva e passa a usar.
        Devolve quantos certificados reais entraram."""
        paginas, rotulos = self._carregar_ficticios(progresso)
        oficiais = correcoes_oficiais(self.pastas)
        reais = [marcacao_de_dados(d) for _, d in sorted(oficiais.items())]
        progresso(f"Treinando o modelo ({len(paginas)} fictícios + {len(reais)} reais corrigidos)")
        modelo = treinar_com_correcoes(paginas, rotulos, reais)
        self.pastas.modelo.parent.mkdir(parents=True, exist_ok=True)
        ml.salvar(modelo, self.pastas.modelo)
        self._arquivo_assinatura().write_text(assinatura_das_correcoes(oficiais),
                                              encoding="utf-8")
        self.modelo = modelo
        return len(reais)

    def _arquivo_assinatura(self) -> Path:
        return self.pastas.modelo.with_suffix(".correcoes.txt")

    def versao_do_modelo(self) -> str:
        """Identifica o modelo em uso: quando foi treinado + começo da assinatura."""
        if not self.pastas.modelo.exists():
            return "—"
        quando = datetime.fromtimestamp(self.pastas.modelo.stat().st_mtime)
        arquivo = self._arquivo_assinatura()
        assinatura = arquivo.read_text(encoding="utf-8")[:8] if arquivo.exists() else "?"
        return f"{quando:%Y-%m-%d %H:%M} ({assinatura})"

    def precisa_aprender(self) -> bool:
        """As correções oficiais mudaram desde o último treino (registro novo, Lixeira…)?"""
        arquivo = self._arquivo_assinatura()
        atual = assinatura_das_correcoes(correcoes_oficiais(self.pastas))
        return not arquivo.exists() or arquivo.read_text(encoding="utf-8") != atual

    def _modelo_em_dia(self, modelo) -> bool:
        """O modelo salvo serve se foi treinado com as correções oficiais de agora e conhece
        todos os rótulos usados nelas (um modelo de antes da etapa 8 não conhecia os padrões)."""
        if self.precisa_aprender():
            return False
        conhecidos = set(getattr(modelo, "classes_", ()))
        usados = {it["certo"] for d in correcoes_oficiais(self.pastas).values()
                  for it in d["palavras"]}
        return usados <= conhecidos

    def preparar_modelo(self, progresso: Progresso = _nada) -> str:
        """Usa o modelo salvo, se existir; senão treina o base. Devolve "salvo" ou "treinado"."""
        if self.pastas.modelo.exists():
            try:
                modelo = ml.abrir(self.pastas.modelo)
            except Exception:  # arquivo estragado ou de outra versão do scikit-learn
                progresso("O modelo salvo não abriu; treinando de novo")
            else:
                if self._modelo_em_dia(modelo):
                    self.modelo = modelo
                    return "salvo"
                progresso("O modelo salvo é antigo (há correções ou rótulos novos); treinando")
        self.aprender(progresso)
        return "treinado"

    # -- análise --------------------------------------------------------------------------
    def analisar(self, caminho: Path | str, progresso: Progresso = _nada) -> Analise:
        if self.modelo is None:
            raise RuntimeError("o modelo ainda não está pronto")
        caminho = Path(caminho)
        progresso("Lendo o certificado (o OCR pode levar alguns segundos)")
        pagina = ler_pdf(caminho)[0]  # só a primeira página nesta versão
        # análise nova: o rascunho de uma análise anterior não registrada é jogado fora
        # (correção sem registro vale só para aquela análise na tela; decisão de 2026-11-17)
        arquivo_de_correcoes(self.pastas, caminho).unlink(missing_ok=True)
        dados = _ler_arquivo(self.pastas, caminho)
        analise = Analise(
            caminho=caminho, pagina=pagina, imagem=renderizar_folha(caminho, pagina.rotacao),
            previsoes=[], rotulos=[], manual=dict(dados.get("manual", {})),
            textos_certos=_textos_existentes(dados, pagina))
        progresso("Descobrindo o que é cada palavra")
        # o modelo olha a página com os textos já corrigidos à mão (se houver)
        analise.previsoes = ml.prever(self.modelo, analise.pagina_corrigida())
        analise.rotulos = [r for r, _ in analise.previsoes]
        corrigidas = _correcoes_existentes(dados, pagina)
        for i, certo in corrigidas.items():
            analise.rotulos[i] = certo
        analise.corrigidas = set(corrigidas)
        progresso("Conferindo com o plano")
        self.recalcular(analise)
        return analise

    def recalcular(self, analise: Analise) -> None:
        """Lê de novo os campos e os pontos (com os textos corrigidos à mão) e confere. Rápido:
        não refaz o OCR, por isso pode rodar direto na tela depois de uma correção de texto."""
        pagina = analise.pagina_corrigida()
        analise.campos = ml.ler_campos(self.modelo, pagina)
        analise.certificado = montar_certificado(self.modelo, pagina)
        self.reconferir(analise)

    def reconferir(self, analise: Analise) -> None:
        """Confere de novo com o plano, usando os valores digitados à mão no lugar do que o
        modelo leu. É rápido (só o banco), por isso pode rodar direto na tela."""
        analise.avisos = [a for a in analise.avisos if not a.startswith("O banco")]
        analise.conferencia = None
        if analise.certificado is None:
            return
        certificado = analise.certificado
        if analise.manual.get("codigo"):
            # sem os textos da folha: o `conferir` não procura outro código, vale o digitado
            certificado = dataclasses.replace(certificado, codigo=analise.manual["codigo"],
                                              textos=())
        if analise.manual.get("faixa"):
            certificado = dataclasses.replace(certificado, faixa=analise.manual["faixa"])
        if analise.manual.get("data_calibracao"):
            certificado = dataclasses.replace(certificado,
                                              data_calibracao=analise.manual["data_calibracao"])
        if not self.pastas.banco.exists():
            analise.avisos.append("O banco dos planos não foi encontrado: a conferência "
                                  "com o plano não foi feita.")
            return
        # O banco é aberto aqui, na mesma thread que o usa (o SQLite não deixa trocar de thread)
        planos = PlanosDQ05(self.pastas.banco)
        try:
            analise.conferencia = conferir(
                certificado, planos,
                padroes_calibrados=analise.manual.get("padroes_calibrados") == "sim")
        except Exception as erro:  # a tela nunca cai por causa de um certificado estranho
            analise.avisos.append(f"Não consegui conferir com o plano: {erro}")
        finally:
            planos.fechar()

    # -- registro (etapa 10) --------------------------------------------------------------
    @property
    def registro(self) -> RegistroAnalises:
        return RegistroAnalises(self.pastas.registro)

    def registrar(self, analise: Analise) -> int:
        """Guarda a análise no registro e devolve o número dela. As correções feitas nesta
        análise passam a ser oficiais (ensinam o modelo no próximo treino)."""
        dados = _ler_arquivo(self.pastas, analise.caminho)
        itens = dados.get("palavras", [])
        correcoes = sum(i["certo"] != i["rotulo"] for i in itens)
        textos = sum(bool(i.get("texto_certo")) for i in itens)
        # a folha corrigida (com o digitado à mão, para voltar ao reabrir); só o que tem
        # correção de rótulo ou de texto ensina o modelo
        marcacao = dados if (correcoes or textos or analise.manual) else None
        c = analise.conferencia
        numero_registro = self.registro.registrar(
            usuario=_usuario(), pc=_computador(), certificado=analise.caminho.name,
            chave=analise.caminho.stem, sha256=_sha256(analise.caminho),
            codigo=c.codigo if c else analise.manual.get("codigo") or analise.campos.get("codigo"),
            plano=c.plano_nome if c else None,
            parecer=c.resultado.value if c else None,
            motivos={"erros": list(c.erros) if c else [],
                     "avisos": (list(c.avisos) if c else []) + list(analise.avisos)},
            lido=_o_que_foi_lido(analise), correcoes=correcoes, textos=textos,
            manual=dict(analise.manual), marcacao=marcacao,
            versao_programa=__version__, versao_modelo=self.versao_do_modelo())
        # registrado: o rascunho já é oficial
        arquivo_de_correcoes(self.pastas, analise.caminho).unlink(missing_ok=True)
        # a cópia do PDF com os checks, para o auditor ver o que foi conferido (etapa 11)
        try:
            self.registro.guardar_conferido(numero_registro,
                                            self._guardar_conferido(numero_registro, analise))
        except Exception:  # sem a cópia o registro continua valendo; só não dá para aprovar
            pass
        return numero_registro

    @property
    def pasta_registro(self) -> Path:
        return self.pastas.registro.parent

    def _guardar_conferido(self, numero_registro: int, analise: Analise) -> str:
        from ..carimbo import sobrepor
        from .folha_conferida import desenhar_marcas, marcas_da_analise

        nome = f"conferidos/{numero_registro:05d}_{analise.caminho.name}"
        largura, altura = analise.imagem.size
        marcas = desenhar_marcas(marcas_da_analise(analise), altura / largura)
        sobrepor(analise.caminho, self.pasta_registro / nome, [(marcas, 0, 0, 1)],
                 analise.pagina.rotacao)
        return nome

    def arquivo_do_registro(self, nome: str | None) -> Path | None:
        """O caminho de um PDF guardado pelo registro (conferido ou aprovado), se existe."""
        if not nome:
            return None
        caminho = self.pasta_registro / nome
        return caminho if caminho.exists() else None

    def aprovar(self, id_: int, nome: str, re: str, data: str) -> Path:
        """Aprovação final pelo responsável: carimba a cópia conferida (checks) com o nome,
        o RE e a data, e o registro passa a constar APROVADO."""
        from ..carimbo import carimbar_pdf

        r = self.registro.obter(id_)
        if r is None:
            raise ValueError("registro não encontrado")
        conferido = self.arquivo_do_registro(r.arquivo_conferido)
        if conferido is None:
            raise ValueError("este registro é de antes da aprovação existir e não tem a cópia "
                             "do PDF com os checks: abra o certificado e registre de novo")
        destino = f"aprovados/{id_:05d}_{r.certificado}"
        carimbar_pdf(conferido, self.pasta_registro / destino, nome.strip(), re.strip(),
                     data.strip(), int(r.lido.get("rotacao", 0)))
        self.registro.aprovar(id_, nome=nome.strip(), re=re.strip(), data=data.strip(),
                              usuario=_usuario(), pc=_computador(), arquivo=destino)
        return self.pasta_registro / destino

    def apagar_aprovacao(self, id_: int) -> None:
        r = self.registro.obter(id_)
        if r is None:
            return
        arquivo = self.arquivo_do_registro(r.arquivo_aprovado)
        self.registro.apagar_aprovacao(id_)
        if arquivo is not None:
            arquivo.unlink(missing_ok=True)


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME", "?")


def _computador() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname()


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 16), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _o_que_foi_lido(analise: Analise) -> dict:
    """O que o programa leu e conferiu, em texto (para o registro)."""
    pontos = [{"nominal": linha.nominal, "encontrado": linha.encontrado, "erro": linha.erro,
               "incerteza": linha.incerteza, "erro_mais_u": linha.erro_mais_u,
               "tolerancia": linha.tolerancia, "criterio": linha.criterio,
               "resultado": linha.resultado.value, "motivo": linha.motivo}
              for linha in descrever_pontos(analise.conferencia)]
    padroes = [{"codigo": p.codigo, "validade": p.validade, "situacao": p.situacao.value}
               for p in descrever_padroes(analise.conferencia)]
    return {"campos": dict(analise.campos), "pontos": pontos, "padroes": padroes,
            "rotacao": analise.pagina.rotacao}


# ---------------------------------------------------------------- texto para a tela

def numero(x: float | None) -> str:
    """Número no jeito brasileiro (vírgula), sem zeros sobrando: 0.0500 → "0,05"."""
    if x is None:
        return "—"
    texto = f"{x:.6f}".rstrip("0").rstrip(".")
    if texto in ("-0", ""):
        texto = "0"
    return texto.replace(".", ",")


def graus_minutos(x: float | None) -> str:
    """Ângulo do goniômetro como está no certificado: 0.0667 → "0°04'", -0.0167 → "-0°01'"."""
    if x is None:
        return "—"
    minutos = round(abs(x) * 60)
    sinal = "-" if x < 0 and minutos else ""
    return f"{sinal}{minutos // 60}°{minutos % 60:02d}'"


def descrever_tolerancia(inferior: float | None, superior: float | None) -> str:
    if inferior is None and superior is None:
        return "—"
    mais = f"+{numero(superior)}" if superior is not None else "∞"
    menos = numero(inferior) if inferior is not None else "−∞"
    return f"{menos} a {mais}"


@dataclass
class LinhaPonto:
    """Um ponto conferido, já em texto para a tabela, a dica e o quadrinho do clique."""

    nominal: str
    encontrado: str
    erro: str
    incerteza: str
    erro_mais_u: str
    tolerancia: str
    resultado: Resultado
    motivo: str
    caixa: tuple[float, float, float, float]
    avisos: list[str]
    # certeza do modelo nas palavras deste ponto, por coluna ("nominal", "erro"…): a menor
    certezas: dict[str, float] = field(default_factory=dict)
    # critério de aceitação ± do certificado ("" quando o laboratório não informa; ADR 0009)
    criterio: str = ""
    criterio_diferente: bool = False  # diferente da tolerância do plano → amarelo

    def dica(self) -> str:
        parecer = self.resultado.value + (f" ({self.motivo})" if self.motivo else "")
        linhas = [f"Ponto {self.nominal}", f"Erro: {self.erro}",
                  f"U (incerteza): {self.incerteza}", f"Erro ± U: {self.erro_mais_u}",
                  f"Tolerância do plano: {self.tolerancia}"]
        if self.criterio:
            linhas.append(f"Critério do certificado: {self.criterio}"
                          + (" (diferente do plano)" if self.criterio_diferente else ""))
        linhas += [f"Parecer: {parecer}", "Clique para ver os detalhes"]
        return "\n".join(linhas + [f"Aviso: {a}" for a in self.avisos])


def _certezas_da_linha(analise: Analise, caixa: tuple[float, ...]) -> dict[str, float]:
    """A menor certeza do modelo em cada coluna do ponto (palavras dentro da linha)."""
    e, t, d, b = caixa
    certezas: dict[str, float] = {}
    for i, palavra in enumerate(analise.pagina.palavras):
        cx, cy = palavra.centro
        rotulo = analise.rotulos[i]
        if rotulo.startswith("ponto.") and e - 0.005 <= cx <= d + 0.005 and t <= cy <= b:
            coluna = rotulo.removeprefix("ponto.")
            certezas[coluna] = min(certezas.get(coluna, 1.0), analise.certeza(i))
    return certezas


def texto_erro_com_incerteza(p: PontoConferido, fmt=numero) -> str:
    """O "Erro ± U" igual ao do programa de calibração: o lado mais perto da tolerância
    (erro −1 e U 1 → "-2"); "± U" só quando o erro é zero."""
    plano = p.plano
    final = erro_com_incerteza(
        p.erro, p.lido.incerteza,
        plano.tolerancia_inferior if plano else None,
        plano.tolerancia_superior if plano else None,
        plano.sem_incerteza if plano else False)
    if final is None:
        return "—"
    return f"± {fmt(final.valor)}" if final.dos_dois_lados else fmt(final.valor)


_UNIDADE = re.compile(r"\d\s*(°|mm|µm|μm|um|cm|kgf\.?\s?m|kgf|N\.?\s?m|kPa|MPa|bar|psi|g|kg|N|m)"
                      r"(?![A-Za-zÀ-ú])")


def unidade_dos_pontos(analise: Analise | None) -> str:
    """A unidade dos valores dos pontos (ex.: "mm"), pelo que o certificado diz na faixa ou
    na resolução; se não achar, pelo cadastro. "" quando não se sabe (ou quando é em graus:
    aí o ° já aparece em cada valor)."""
    if analise is None:
        return ""
    c = analise.conferencia
    if c and any(p.lido.graus_minutos or p.lido.escala for p in c.pontos):
        return ""  # em graus o ° já vem no valor; no durômetro cada ponto tem a sua escala
    textos = [analise.manual.get("resolucao"), analise.manual.get("faixa"),
              analise.campos.get("resolucao"), analise.campos.get("faixa")]
    if c:
        textos += [c.faixa_certificado, c.cadastro.get("resolucao"), c.cadastro.get("faixa"),
                   c.faixa_plano]
    for texto in textos:
        achou = _UNIDADE.search(str(texto or ""))
        if achou:
            unidade = achou.group(1).replace(" ", "")
            return "µm" if unidade in ("um", "μm") else unidade
    return ""


def descrever_pontos(conferencia: Conferencia | None,
                     analise: Analise | None = None) -> list[LinhaPonto]:
    if conferencia is None:
        return []
    # a unidade junto de cada valor, para a tabela, a dica e o quadrinho (pedido do usuário,
    # 2026-11-17); em graus o ° já vem no próprio valor
    unidade_geral = unidade_dos_pontos(analise)
    unidade = unidade_geral

    def com(texto: str) -> str:
        vazio = ("", "—", "fora do plano")
        espaco = "" if unidade == "°" else " "  # 12,5° (grau grudado no número)
        return f"{texto}{espaco}{unidade}" if unidade and texto not in vazio else texto

    linhas = []
    for p in conferencia.pontos:
        av: Avaliacao = p.avaliacao
        # goniômetro em graus°minutos': mostra igual ao certificado (pedido do usuário,
        # 2026-11-16); a tolerância é a do plano, como está no cadastro
        fmt = graus_minutos if p.lido.graus_minutos else numero
        unidade = p.lido.escala or unidade_geral  # durômetro: a escala da linha (HR15T…)
        faixa = texto_erro_com_incerteza(p, fmt)
        tol = (descrever_tolerancia(p.plano.tolerancia_inferior, p.plano.tolerancia_superior)
               if p.plano else "fora do plano")
        if p.plano and p.lido.graus_minutos and tol != "—":  # plano em graus decimais
            tol = " a ".join(f"{lado}°" for lado in tol.split(" a "))
        linhas.append(LinhaPonto(
            nominal=com(fmt(p.lido.nominal)), encontrado=com(fmt(p.lido.encontrado)),
            erro=com(fmt(p.erro)), incerteza=com(fmt(p.lido.incerteza)),
            erro_mais_u=com(faixa), tolerancia=com(tol),
            resultado=av.resultado, motivo=av.motivo or "",
            caixa=p.lido.caixa, avisos=list(p.avisos),
            certezas=_certezas_da_linha(analise, p.lido.caixa) if analise else {},
            criterio=(com(descrever_criterio(p.lido.criterio))
                      if p.lido.criterio is not None else ""),
            criterio_diferente=p.criterio == SituacaoCriterio.DIFERENTE))
    return linhas


@dataclass
class LinhaPadrao:
    """Um padrão conferido, já em texto para a caixa "Padrões" e a marca na folha."""

    codigo: str
    validade: str  # como está escrita + até quando vale, se só tem mês/ano
    situacao: SituacaoPadrao
    dica: str
    caixa: tuple[float, float, float, float] | None


def descrever_padroes(conferencia: Conferencia | None) -> list[LinhaPadrao]:
    if conferencia is None or conferencia.padroes is None:
        return []
    data_cal = conferencia.padroes.data_calibracao
    linhas = []
    for p in conferencia.padroes.padroes:
        validade = p.validade_texto or "não lida"
        if p.validade and p.validade.so_mes:
            validade += f" (até {data_br(p.validade.ate)})"
        if p.situacao == SituacaoPadrao.EM_DIA:
            dica = f"Em dia: vale até {data_br(p.validade.ate)}; calibração em {data_br(data_cal)}"
        elif p.situacao == SituacaoPadrao.VENCIDO:
            dica = (f"Vencido: valia até {data_br(p.validade.ate)} e a calibração foi em "
                    f"{data_br(data_cal)}. Se os pontos passam, o parecer fica PENDENTE; se "
                    "reprovam, continua REPROVADO")
        else:
            dica = f"Não conferido: {p.motivo} (só avisa: o parecer não muda)"
        linhas.append(LinhaPadrao(p.codigo or "sem código", validade, p.situacao,
                                  f"Padrão {p.codigo or 'sem código'}\n{dica}", p.caixa))
    return linhas
