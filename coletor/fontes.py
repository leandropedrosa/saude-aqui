"""
Acesso às fontes de dados:

* FTP do DATASUS: arquivos mensais de profissionais (PFufAAMM.dbc)
* API de dados abertos do Ministério da Saúde: estabelecimentos
* Portal de escalas da Prefeitura (NúcleoGov): lista de escalas e arquivos anexos

Só funções de download aqui; a interpretação dos dados fica em transformar.py.
"""

import hashlib
import json
import logging
import re
import time
from ftplib import FTP
from pathlib import Path
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- FTP (profissionais)

def _conectar_ftp(url_pasta: str) -> FTP:
    """Conecta no FTP anônimo e entra na pasta indicada pela URL."""
    url = urlparse(url_pasta)
    ftp = FTP(url.hostname, timeout=120)
    ftp.login()  # anônimo
    ftp.cwd(url.path)
    return ftp


def competencias_disponiveis(url_pasta: str, uf: str) -> list[str]:
    """Lista as competências publicadas no FTP, ex.: ['2609', '2608', ...] (mais recente primeiro)."""
    with _conectar_ftp(url_pasta) as ftp:
        nomes = ftp.nlst()
    padrao = re.compile(rf"^PF{uf}(\d{{4}})\.dbc$", re.IGNORECASE)
    return sorted((m.group(1) for n in nomes if (m := padrao.match(n))), reverse=True)


def baixar_pf(url_pasta: str, uf: str, aamm: str, pasta_destino: Path) -> Path:
    """Baixa PF{uf}{aamm}.dbc para a pasta de destino e devolve o caminho."""
    pasta_destino.mkdir(parents=True, exist_ok=True)
    nome = f"PF{uf}{aamm}.dbc"
    destino = pasta_destino / nome
    temporario = destino.with_suffix(".parcial")
    log.info("Baixando %s%s ...", url_pasta, nome)
    with _conectar_ftp(url_pasta) as ftp, open(temporario, "wb") as arquivo:
        ftp.retrbinary(f"RETR {nome}", arquivo.write)
    temporario.replace(destino)  # só "aparece" quando o download terminou
    log.info("Baixado: %s (%.1f MB)", destino, destino.stat().st_size / 1e6)
    return destino


def sha256(caminho: Path) -> str:
    """Hash SHA-256 do arquivo, lido em blocos (não carrega tudo na memória)."""
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------- API (estabelecimentos)

def buscar_estabelecimentos(url_api: str, municipio_ibge: str) -> list[dict]:
    """Busca todos os estabelecimentos do município na API (paginada de 20 em 20)."""
    todos: list[dict] = []
    pagina = 20
    with httpx.Client(timeout=60) as cliente:
        for deslocamento in range(0, 5000, pagina):
            dados = _get_com_tentativas(cliente, url_api, {
                "codigo_municipio": municipio_ibge, "limit": pagina, "offset": deslocamento,
            })
            lote = dados.get("estabelecimentos", [])
            todos.extend(lote)
            if len(lote) < pagina:
                break
    log.info("API do CNES: %d estabelecimentos no município %s", len(todos), municipio_ibge)
    return todos


def _get_com_tentativas(cliente: httpx.Client, url: str, params: dict, tentativas: int = 3) -> dict:
    """GET com até 3 tentativas: a API do Ministério às vezes demora ou falha."""
    for n in range(1, tentativas + 1):
        try:
            resposta = cliente.get(url, params=params)
            resposta.raise_for_status()
            return resposta.json()
        except httpx.HTTPError as erro:
            if n == tentativas:
                raise
            log.warning("Falha na API (%s), tentativa %d de %d", erro, n, tentativas)
            time.sleep(5 * n)
    raise RuntimeError("inalcançável")


# ---------------------------------------------------------------- portal da Prefeitura

# O servidor do portal responde 403 para clientes "estranhos": nos identificamos como navegador
_UA_NAVEGADOR = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


def buscar_escalas_portal(url_portal: str) -> list[dict]:
    """Lista todas as escalas publicadas no portal (a mesma chamada que a página faz)."""
    parametros = {"q": {"limit": "0, 500", "acao": "escalasmedicas/listarCidadao"}}
    cabecalhos = {"User-Agent": _UA_NAVEGADOR, "X-Requested-With": "XMLHttpRequest",
                  "Referer": f"{url_portal}/cidadao/outras_informacoes/escalasmedicas"}
    with httpx.Client(headers=cabecalhos, timeout=60) as cliente:
        resposta = cliente.post(f"{url_portal}/api",
                                data={"multi_request": "true", "params": json.dumps(parametros)})
        resposta.raise_for_status()
        escalas = resposta.json()["q"]["dados"]
    log.info("Portal da Prefeitura: %d escalas publicadas", len(escalas))
    return escalas


def baixar_arquivo_portal(url_arquivos: str, midia: str) -> bytes:
    """Baixa um anexo do portal. O link assinado falha com acentos, então usamos o endereço público."""
    resposta = httpx.get(f"{url_arquivos}{midia}", timeout=60)
    resposta.raise_for_status()
    return resposta.content
