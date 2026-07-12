"""Revisita a URL dos itens que sumiram do scrape e marca os que venderam/saíram.

O acervo (data/coleta-classificada.json) acumula tudo que já vimos. Um item
'ativo' que NÃO aparece no scrape atual pode ter: (a) vendido, (b) sido removido,
ou (c) só envelhecido pra fora do top-200 mais recentes. Só dá pra saber
revisitando a página do anúncio.

Conservador de propósito: só marca 'vendido'/'removido' com sinal CLARO
(404, sem título, badge de vendido ou ausência do botão de compra). Qualquer
erro de rede/ambiguidade mantém 'ativo' — melhor um falso-ativo do que sumir
com um item que ainda está à venda.

Uso:
    python -m src.scrape.verifica_vendidos [--marca sundek|ville] [--max N]
    HEADLESS=true python -m src.scrape.verifica_vendidos --marca ville

Padrões: --marca sundek, --max 80. A sessão da Vinted é a mesma pras duas marcas
(só muda quais arquivos de acervo/scrape são lidos e regravados).
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..utils.browser import abrir_sessao_vinted

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


def _checar_status(page, url: str) -> str:
    """Revisita a página do item e retorna 'vendido' | 'removido' | 'ativo'."""
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        return "ativo"  # erro de rede/timeout → não muda (evita falso vendido)

    if resp is not None and resp.status >= 400:
        return "removido"  # 404/410 — anúncio apagado

    page.wait_for_timeout(800)
    try:
        info = page.evaluate("""() => {
            const has = (s) => !!document.querySelector(s);
            const title = document.querySelector('[data-testid="item-page-title"], h1');
            const statusTxt = (
                document.querySelector('[data-testid="item-status"]')?.textContent || ''
            ).toLowerCase();
            return {
                temTitulo: !!title,
                podeComprar: has('[data-testid="item-buy-button"]'),
                podeBarganhar: has('[data-testid="item-buyer-offer-button"]'),
                statusTxt,
            };
        }""")
    except Exception:
        # Um redirect/navegação da página (login, consentimento, SPA) destrói o
        # contexto de execução e o evaluate lança. Mesma regra do goto: erro/dúvida
        # mantém 'ativo' — melhor um falso-ativo do que sumir com algo à venda.
        return "ativo"

    if not info["temTitulo"]:
        return "removido"
    # badge explícito de vendido (es/en/fr/it)
    if any(k in info["statusTxt"] for k in ("vendido", "sold", "vendu", "venduto")):
        return "vendido"
    # título existe mas sumiram as ações de compra/oferta → vendido/indisponível
    if not info["podeComprar"] and not info["podeBarganhar"]:
        return "vendido"
    return "ativo"


# Arquivos por marca: (acervo classificado a ser atualizado, scrape atual p/ ids ativos).
ARQUIVOS = {
    "sundek": ("coleta-classificada.json", "coleta.json"),
    "ville": ("coleta-ville-classificada.json", "coleta-ville.json"),
}


def main() -> None:
    # args: --marca sundek|ville (padrão sundek) e --max N (padrão 80).
    argv = sys.argv[1:]
    marca = "sundek"
    max_check = 80
    for i, arg in enumerate(argv):
        if arg == "--marca" and i + 1 < len(argv):
            marca = argv[i + 1]
        elif arg == "--max" and i + 1 < len(argv):
            max_check = int(argv[i + 1])
    if marca not in ARQUIVOS:
        print(f"marca inválida: {marca!r} (use: {', '.join(ARQUIVOS)})")
        sys.exit(1)

    acervo_nome, scrape_nome = ARQUIVOS[marca]
    caminho = DATA / acervo_nome
    if not caminho.exists():
        print(f"{acervo_nome} não encontrado.")
        sys.exit(1)

    acervo = json.loads(caminho.read_text())

    # ids vistos no scrape atual (esses estão comprovadamente ativos)
    ids_scrape: set[str] = set()
    col = DATA / scrape_nome
    if col.exists():
        try:
            ids_scrape = {x.get("id") for x in json.loads(col.read_text()) if x.get("id")}
        except Exception:
            pass

    # candidatos: 'ativo' (ou sem status) que sumiram do scrape e têm URL.
    # Prioriza os não verificados / vistos há mais tempo.
    candidatos = [
        x for x in acervo
        if x.get("status", "ativo") == "ativo"
        and x.get("id") not in ids_scrape
        and x.get("url")
    ]
    candidatos.sort(key=lambda x: x.get("verificado_em") or x.get("ultimo_visto") or "")
    candidatos = candidatos[:max_check]

    print(f"=== Verifica vendidos [{marca}] · acervo {len(acervo)} · "
          f"{len(candidatos)} candidatos (sumiram do scrape) ===\n")
    if not candidatos:
        print("  nada a verificar.")
        return

    agora = datetime.now(timezone.utc).isoformat()
    mudancas = {"vendido": 0, "removido": 0, "ativo": 0}

    with sync_playwright() as p:
        browser, _, page = abrir_sessao_vinted(p)
        for i, item in enumerate(candidatos):
            status = _checar_status(page, item["url"])
            item["status"] = status if status != "ativo" else "ativo"
            item["verificado_em"] = agora
            mudancas[status] += 1
            print(f"  [{i+1}/{len(candidatos)}] {status:<8} {(item.get('titulo') or '')[:45]}")
            time.sleep(0.4)
        browser.close()

    caminho.write_text(json.dumps(acervo, indent=2, ensure_ascii=False))
    print(f"\n=== Resumo ===")
    print(f"  vendido:  {mudancas['vendido']}")
    print(f"  removido: {mudancas['removido']}")
    print(f"  segue ativo (só envelheceu): {mudancas['ativo']}")
    print(f"\n  Salvo em data/coleta-classificada.json")


if __name__ == "__main__":
    main()
