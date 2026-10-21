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
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..utils.browser import abrir_sessao_vinted

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


# Selos exatos (texto inteiro do elemento, sem pontuação) — es/en/fr/it/nl/de/pt/pl.
_SELO_REMOVIDO = {"eliminado", "deleted", "removed", "supprimé", "supprime", "eliminato",
                  "verwijderd", "gelöscht", "geloscht", "usunięte", "usuniete"}
_SELO_VENDIDO = {"vendido", "sold", "vendu", "venduto", "verkocht", "verkauft", "sprzedane"}


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
            // Selo solto na foto ("¡Eliminado!", "Vendido"...): em out/2026 o Vinted não usa
            // mais o item-status e mantém os botões de compra na página de anúncio apagado.
            // Só no topo da página (sobre a foto principal): os carrosséis de "similares" /
            // "mais do vendedor" mais abaixo têm selos de OUTROS anúncios.
            const selos = [...document.querySelectorAll('span, div')]
                .filter(e => e.children.length === 0)
                .filter(e => { const r = e.getBoundingClientRect(); return r.height > 0 && r.top + window.scrollY < 900; })
                .map(e => (e.textContent || '').trim().toLowerCase())
                .filter(t => t.length > 0 && t.length <= 20);
            return {
                temTitulo: !!title,
                podeComprar: has('[data-testid="item-buy-button"]'),
                podeBarganhar: has('[data-testid="item-buyer-offer-button"]'),
                statusTxt,
                selos,
            };
        }""")
    except Exception:
        # Um redirect/navegação da página (login, consentimento, SPA) destrói o
        # contexto de execução e o evaluate lança. Mesma regra do goto: erro/dúvida
        # mantém 'ativo' — melhor um falso-ativo do que sumir com algo à venda.
        return "ativo"

    if not info["temTitulo"]:
        return "removido"
    selo = {re.sub(r"[¡!¿?.\s]", "", t) for t in info.get("selos") or []}
    if selo & _SELO_REMOVIDO:
        return "removido"
    if selo & _SELO_VENDIDO:
        return "vendido"
    # badge explícito de vendido (es/en/fr/it)
    if any(k in info["statusTxt"] for k in ("vendido", "sold", "vendu", "venduto")):
        return "vendido"
    # título existe mas sumiram as ações de compra/oferta → vendido/indisponível
    if not info["podeComprar"] and not info["podeBarganhar"]:
        return "vendido"
    return "ativo"


_JS_DADOS = """() => ({
  fotos: [...document.querySelectorAll('img')]
    .filter(i => i.src.includes('images1.vinted.net') && i.src.includes('/f800/')
                 && i.getBoundingClientRect().top + window.scrollY < 1100 && i.width > 120)
    .map(i => i.src),
  preco: (document.querySelector('[data-testid="item-price"]')?.textContent || '').trim()
})"""


def _preco_float(txt: str | None) -> float | None:
    t = re.sub(r"\.(?=\d{3}\b)", "", (txt or "").replace("\xa0", " "))  # 1.234,00 → 1234,00
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", t)
    return float(m.group(1).replace(",", ".")) if m else None


def _atualizar_dados(page, item: dict) -> str:
    """Anúncio ATIVO: atualiza fotos e preço com o que está na página. O Vinted troca o endereço
    das fotos com o tempo (o link guardado dá 404 e o app mostra foto quebrada) e o vendedor baixa
    o preço. Retorna um resumo curto do que mudou ("" se nada)."""
    try:
        d = page.evaluate(_JS_DADOS)
    except Exception:
        return ""
    mud = []
    fotos = list(dict.fromkeys(d.get("fotos") or []))
    chave = lambda u: u.split("/f800/")[-1].split("?")[0]
    if fotos and [chave(u) for u in fotos] != [chave(u) for u in (item.get("fotos") or [])]:
        item["fotos"] = fotos
        mud.append("fotos")
    novo = _preco_float(d.get("preco"))
    velho = _preco_float(item.get("preco"))
    if novo and velho and abs(novo - velho) >= 0.01:
        item.setdefault("preco_inicial", item.get("preco"))
        item["preco"] = f"{novo:.2f}".replace(".", ",") + "\xa0€"
        # preço com a taxa do Vinted (5% + €0,70), como o scrape grava
        item["preco_total"] = f"{novo * 1.05 + 0.70:.2f}".replace(".", ",") + "\xa0€"
        mud.append(f"preço {velho:g}→{novo:g}")
    return ", ".join(mud)


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
    # Os que estão NO APP (comprável/barganha) vêm primeiro, revistos a cada 6h: vendido
    # tem que sair do app rápido e foto/preço precisam estar atuais. O resto segue por antiguidade.
    limite = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    no_app = [x for x in candidatos if (x.get("score") or {}).get("decisao") in ("compravel", "medio")
              and (x.get("verificado_em") or "") < limite]
    ids_app = {id(x) for x in no_app}
    candidatos = (no_app + [x for x in candidatos if id(x) not in ids_app])[:max_check]

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
            extra = _atualizar_dados(page, item) if status == "ativo" else ""
            print(f"  [{i+1}/{len(candidatos)}] {status:<8} {(item.get('titulo') or '')[:45]}"
                  + (f"  ({extra})" if extra else ""))
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
