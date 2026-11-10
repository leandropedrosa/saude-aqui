"""
Fase 0 — Investigação da fonte de dados.

Abre o portal de escalas médicas da Prefeitura de Cidade Ocidental em um
navegador headless (Chromium via Playwright) e registra TODAS as requisições
de rede feitas pela página. O objetivo é descobrir de onde vêm as escalas:

  * Caso A: um endpoint JSON/XHR  -> o coletor de produção usa só httpx.
  * Caso B: arquivos anexos (PDF, XLS...) -> baixamos exemplos para estudar.

Este script é usado APENAS na investigação. Em produção não usamos navegador,
porque o Chromium consome centenas de MB de RAM.

Uso:
    python coletor/investigar.py
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_FONTE = (
    "https://acessoainformacao.cidadeocidental.go.gov.br"
    "/cidadao/outras_informacoes/escalasmedicas"
)

PASTA_AMOSTRAS = Path(__file__).parent / "amostras"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)


def main() -> None:
    PASTA_AMOSTRAS.mkdir(exist_ok=True)
    requisicoes = []  # cada item: url, método, tipo, status, content-type, tamanho

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        # O servidor da Prefeitura responde 403 para o user-agent padrão
        # "HeadlessChrome"; por isso nos identificamos como um Chrome comum.
        pagina = navegador.new_page(user_agent=USER_AGENT, locale="pt-BR")

        # Chamado a cada resposta recebida pela página.
        def ao_receber(resposta):
            req = resposta.request
            try:
                corpo = resposta.body()
                tamanho = len(corpo)
            except Exception:
                corpo, tamanho = b"", None
            tipo_conteudo = resposta.headers.get("content-type", "")
            requisicoes.append(
                {
                    "url": req.url,
                    "metodo": req.method,
                    "tipo_recurso": req.resource_type,  # xhr, fetch, document...
                    "status": resposta.status,
                    "content_type": tipo_conteudo,
                    "tamanho": tamanho,
                    "post_data": req.post_data,
                }
            )
            # Guardamos o corpo das respostas JSON para análise.
            if "json" in tipo_conteudo and corpo:
                nome = f"resposta_{len(requisicoes):03d}.json"
                (PASTA_AMOSTRAS / nome).write_bytes(corpo)

        pagina.on("response", ao_receber)
        pagina.goto(URL_FONTE, wait_until="networkidle", timeout=90_000)
        pagina.wait_for_timeout(3000)  # margem para carregamentos tardios

        # Salvamos também o HTML renderizado, os links da página e uma captura.
        (PASTA_AMOSTRAS / "pagina_renderizada.html").write_text(
            pagina.content(), encoding="utf-8"
        )
        links = pagina.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({texto: e.innerText.trim(), href: e.href}))"
        )
        (PASTA_AMOSTRAS / "links.json").write_text(
            json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        pagina.screenshot(path=str(PASTA_AMOSTRAS / "pagina.png"), full_page=True)
        navegador.close()

    (PASTA_AMOSTRAS / "rede.json").write_text(
        json.dumps(requisicoes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(requisicoes)} requisições registradas em amostras/rede.json")
    for r in requisicoes:
        if r["tipo_recurso"] in ("xhr", "fetch", "document"):
            print(f'{r["metodo"]:6} {r["status"]} {r["content_type"][:30]:30} {r["url"]}')


if __name__ == "__main__":
    main()
