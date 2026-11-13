"""O fluxo do programa, sem nada de tela: analisar, corrigir, digitar à mão e aprender.

Tudo aqui pode ser testado sem abrir janela. A interface só chama estas funções (em segundo
plano, porque o OCR e o treino demoram) e desenha o que elas devolvem.

Onde ficam as coisas (todas FORA do Git — ADR 0002; `dados/` e `modelos/` estão no .gitignore):
- `dados/reais_marcacao/<nome>.palavras.json` — as correções feitas à mão (e os valores
  digitados, na chave `manual`);
- `dados/ficticios/` — certificados inventados usados no treino base;
- `dados/banco_dq05/release_1_2_0/calibracao.db` — cópia do banco dos planos (só leitura);
- `modelos/modelo_atual.joblib` — o modelo treinado.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from ..aprendizado import modelo as ml
from ..aprendizado.correcoes import carregar_pasta, treinar_com_correcoes
from ..aprendizado.rotulos import rotular
from ..conferencia.avaliacao import Avaliacao, Resultado
from ..conferencia.conferir import Conferencia, conferir
from ..conferencia.extracao import CertificadoLido, montar_certificado
from ..conferencia.plano import PlanosDQ05
from ..ficticio.gerar import gerar_um
from ..leitura import Pagina
from ..leitura.ler import ler_pdf

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
}

# O que dá para digitar à mão quando o modelo não consegue ler (ex.: código escrito a caneta).
CAMPOS_MANUAIS: dict[str, str] = {"codigo": "Código do instrumento", "faixa": "Faixa"}


@dataclass
class Pastas:
    """Onde o programa lê e grava. Nos testes aponta para uma pasta temporária."""

    marcacao: Path = RAIZ / "dados" / "reais_marcacao"
    ficticios: Path = RAIZ / "dados" / "ficticios"
    banco: Path = RAIZ / "dados" / "banco_dq05" / "release_1_2_0" / "calibracao.db"
    modelo: Path = RAIZ / "modelos" / "modelo_atual.joblib"
    quantidade_ficticios: int = 150  # tantos certificados inventados no treino


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
    return pastas.marcacao / f"{certificado.stem}.palavras.json"


def _lido_confere(itens: list[dict], pagina: Pagina) -> bool:
    """O JSON guardado é desta mesma leitura? (mesmo número de palavras e mesmos textos)"""
    return len(itens) == len(pagina.palavras) and all(
        i["texto"] == p.texto for i, p in zip(itens, pagina.palavras, strict=True))


def _ler_arquivo(pastas: Pastas, caminho: Path) -> dict:
    arquivo = arquivo_de_correcoes(pastas, caminho)
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}


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
    pastas.marcacao.mkdir(parents=True, exist_ok=True)
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
    if campo not in CAMPOS_MANUAIS:
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
        """Lê os certificados inventados (gera os que faltam). Fica em memória para os próximos
        treinos — ler 150 PDFs é a parte lenta."""
        if self._ficticios is None:
            paginas, rotulos = [], []
            total = self.pastas.quantidade_ficticios
            for n in range(1, total + 1):
                if n % 10 == 1:
                    progresso(f"Preparando certificados de treino ({n} de {total})")
                gabarito = self.pastas.ficticios / f"cert_{n:04d}.json"
                if not gabarito.exists():
                    gerar_um(self.pastas.ficticios, n)
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
        reais = carregar_pasta(self.pastas.marcacao) if self.pastas.marcacao.exists() else []
        progresso(f"Treinando o modelo ({len(paginas)} fictícios + {len(reais)} reais corrigidos)")
        modelo = treinar_com_correcoes(paginas, rotulos, reais)
        self.pastas.modelo.parent.mkdir(parents=True, exist_ok=True)
        ml.salvar(modelo, self.pastas.modelo)
        self.modelo = modelo
        return len(reais)

    def preparar_modelo(self, progresso: Progresso = _nada) -> str:
        """Usa o modelo salvo, se existir; senão treina o base. Devolve "salvo" ou "treinado"."""
        if self.pastas.modelo.exists():
            try:
                self.modelo = ml.abrir(self.pastas.modelo)
                return "salvo"
            except Exception:  # arquivo estragado ou de outra versão do scikit-learn
                progresso("O modelo salvo não abriu; treinando de novo")
        self.aprender(progresso)
        return "treinado"

    # -- análise --------------------------------------------------------------------------
    def analisar(self, caminho: Path | str, progresso: Progresso = _nada) -> Analise:
        if self.modelo is None:
            raise RuntimeError("o modelo ainda não está pronto")
        caminho = Path(caminho)
        progresso("Lendo o certificado (o OCR pode levar alguns segundos)")
        pagina = ler_pdf(caminho)[0]  # só a primeira página nesta versão
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
        if not self.pastas.banco.exists():
            analise.avisos.append("O banco dos planos não foi encontrado: a conferência "
                                  "com o plano não foi feita.")
            return
        # O banco é aberto aqui, na mesma thread que o usa (o SQLite não deixa trocar de thread)
        planos = PlanosDQ05(self.pastas.banco)
        try:
            analise.conferencia = conferir(certificado, planos)
        except Exception as erro:  # a tela nunca cai por causa de um certificado estranho
            analise.avisos.append(f"Não consegui conferir com o plano: {erro}")
        finally:
            planos.fechar()


# ---------------------------------------------------------------- texto para a tela

def numero(x: float | None) -> str:
    """Número no jeito brasileiro (vírgula), sem zeros sobrando: 0.0500 → "0,05"."""
    if x is None:
        return "—"
    texto = f"{x:.6f}".rstrip("0").rstrip(".")
    if texto in ("-0", ""):
        texto = "0"
    return texto.replace(".", ",")


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

    def dica(self) -> str:
        parecer = self.resultado.value + (f" ({self.motivo})" if self.motivo else "")
        linhas = [f"Ponto {self.nominal}", f"Erro: {self.erro}",
                  f"U (incerteza): {self.incerteza}", f"Erro ± U: {self.erro_mais_u}",
                  f"Tolerância do plano: {self.tolerancia}", f"Parecer: {parecer}",
                  "Clique para ver os detalhes"]
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


def descrever_pontos(conferencia: Conferencia | None,
                     analise: Analise | None = None) -> list[LinhaPonto]:
    if conferencia is None:
        return []
    linhas = []
    for p in conferencia.pontos:
        av: Avaliacao = p.avaliacao
        faixa = f"{numero(av.faixa[0])} a {numero(av.faixa[1])}" if av.faixa else "—"
        tol = (descrever_tolerancia(p.plano.tolerancia_inferior, p.plano.tolerancia_superior)
               if p.plano else "fora do plano")
        linhas.append(LinhaPonto(
            nominal=numero(p.lido.nominal), encontrado=numero(p.lido.encontrado),
            erro=numero(p.erro), incerteza=numero(p.lido.incerteza), erro_mais_u=faixa,
            tolerancia=tol, resultado=av.resultado, motivo=av.motivo or "",
            caixa=p.lido.caixa, avisos=list(p.avisos),
            certezas=_certezas_da_linha(analise, p.lido.caixa) if analise else {}))
    return linhas
