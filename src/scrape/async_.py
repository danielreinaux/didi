"""Scraper paralelo (asyncio). Mesma lógica do scrape.py mas N tabs em paralelo.

Uso:
    python -m src.scrape_async                  # 3 tabs (default)
    WORKERS=5 python -m src.scrape_async        # 5 tabs
    HEADLESS=true python -m src.scrape_async    # sem janela
"""
import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from ..config import MAX_ITEMS_POR_RODADA, VINTED
from ..utils.historico import atualizar_com_scrape
from ..sources.vinted import montar_url_sundek_hombre

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
SHOTS = DATA / "screenshots"

WORKERS = int(os.environ.get("WORKERS", "3"))
HEADLESS = os.environ.get("HEADLESS", "").lower() == "true"


def _strip_label(text, labels):
    if not text:
        return None
    t = text.strip()
    for lbl in labels:
        if t.startswith(lbl):
            return t[len(lbl):].strip()
    return t


async def extract_item_async(page, url: str) -> dict:
    """Versão async do extract_item — mesma lógica."""
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    await page.wait_for_timeout(1200)

    raw = await page.evaluate("""() => {
      const t = (sel) => document.querySelector(sel)?.textContent?.trim() || null;
      const exists = (sel) => !!document.querySelector(sel);

      const resumo = t('[data-testid="item-page-summary-plugin"]');
      const tituloEl = t('[data-testid="item-page-title"]') ||
        document.querySelector('h1')?.textContent?.trim() || null;

      const tamanhoRaw = t('[data-testid="item-attributes-size"]');
      const estadoRaw  = t('[data-testid="item-attributes-status"]');
      const corRaw     = t('[data-testid="item-attributes-color"]');
      const uploadRaw  = t('[data-testid="item-attributes-upload_date"]');
      const enviRaw    = t('[data-testid="item-shipping-banner-price"]');
      const marcaRaw   = t('[data-testid="item-attributes-brand-menu-button"]');

      // Pega só as fotos da galeria do anúncio (não do vendedor).
      let fotos = [];
      const gallery = document.querySelector('[data-testid="item-photos-area"], [data-testid="image-carousel"]');
      if (gallery) {
        fotos = Array.from(gallery.querySelectorAll('img'))
          .map(img => img.src)
          .filter(u => u.includes('vinted.net') && /\\/f\\d+\\//.test(u));
      }
      if (!fotos.length) {
        const todas = Array.from(document.querySelectorAll('img'))
          .map(img => img.src)
          .filter(u => u.includes('vinted.net') && /\\/f\\d+\\//.test(u));
        const tsRe = /\\/(\\d{10,})\\.webp/;
        const counts = {};
        todas.forEach(u => {
          const m = u.match(tsRe);
          if (m) counts[m[1]] = (counts[m[1]] || 0) + 1;
        });
        const dominante = Object.entries(counts).sort((a,b) => b[1]-a[1])[0]?.[0];
        fotos = todas.filter(u => {
          const m = u.match(tsRe);
          return m && m[1] === dominante;
        });
      }
      fotos = [...new Set(fotos)];

      const preco = t('[data-testid="item-price"]');
      const precoTotal = t('[data-testid="total-combined-price"]');

      const sellerLocation = t('[data-testid="seller-location"]');
      const sellerLastSeen = t('[data-testid="seller-last-logged-in"]');
      let sellerUsername = null, sellerUrl = null;
      const memberLinks = Array.from(document.querySelectorAll('a[href*="/member/"]'))
        .filter(a => !a.href.includes('signup') && !a.href.includes('login'));
      if (memberLinks.length) {
        const link = memberLinks[0];
        sellerUsername = link.querySelector('span')?.textContent?.trim() || link.textContent?.trim();
        sellerUrl = link.href;
      }

      return {
        tituloEl, resumo, tamanhoRaw, estadoRaw, corRaw, uploadRaw, enviRaw, marcaRaw,
        preco, precoTotal,
        sellerUsername, sellerUrl, sellerLocation, sellerLastSeen,
        fotos,
        podeBarganhar: exists('[data-testid="item-buyer-offer-button"]'),
        podeMensagem: exists('[data-testid="ask-seller-button"]'),
        podeComprar: exists('[data-testid="item-buy-button"]'),
      };
    }""")

    item_id_match = re.search(r"/items/(\d+)", url)
    marca_clean = None
    if raw.get("marcaRaw"):
        marca_clean = re.sub(r"Menú de la marca", "", raw["marcaRaw"], flags=re.I).strip()

    return {
        "id": item_id_match.group(1) if item_id_match else None,
        "url": url,
        "titulo": raw.get("tituloEl"),
        "resumo": raw.get("resumo"),
        "marca": marca_clean,
        "tamanho": _strip_label(raw.get("tamanhoRaw"), ["Tamaño", "Talla", "Tamanho", "Size"]),
        "estado": _strip_label(raw.get("estadoRaw"), ["Estado", "Condition"]),
        "cor": _strip_label(raw.get("corRaw"), ["Color"]),
        "upload": _strip_label(raw.get("uploadRaw"), ["Subido", "Uploaded"]),
        "envio": _strip_label(raw.get("enviRaw"), ["Envío", "Shipping"]),
        "preco": raw.get("preco"),
        "preco_total": raw.get("precoTotal"),
        "vendedor": {
            "username": raw.get("sellerUsername"),
            "url": raw.get("sellerUrl"),
            "localizacao": raw.get("sellerLocation"),
            "ultima_visita": raw.get("sellerLastSeen"),
        },
        "fotos_count": len(raw.get("fotos") or []),
        "fotos": (raw.get("fotos") or [])[:8],
        "acoes": {
            "pode_barganhar": raw.get("podeBarganhar"),
            "pode_mensagem": raw.get("podeMensagem"),
            "pode_comprar": raw.get("podeComprar"),
        },
        "coletado_em": datetime.now(timezone.utc).isoformat(),
    }


async def abrir_sessao(playwright):
    """Versão async do browser.abrir_sessao_vinted."""
    browser = await playwright.chromium.launch(headless=HEADLESS, slow_mo=0 if HEADLESS else 60)
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="es-ES",
        user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"),
    )
    page = await context.new_page()
    await page.goto(VINTED["home_url"], wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)
    # selecionar Espanha
    try:
        esp = page.locator('a:has-text("Espanha"), a[href*="vinted.es"]').first
        if await esp.is_visible(timeout=4000):
            await esp.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2000)
    except Exception:
        pass
    # cookies
    for sel in ["#onetrust-accept-btn-handler", 'button:has-text("Aceptar")', 'button:has-text("Accept all")']:
        try:
            b = page.locator(sel).first
            if await b.is_visible(timeout=1500):
                await b.click()
                await page.wait_for_timeout(500)
                break
        except Exception:
            pass
    await page.wait_for_timeout(500)
    try:
        modal = page.locator('[data-testid="country-select-modal"], [role="dialog"]:has-text("Where do you live")')
        if await modal.is_visible(timeout=2000):
            await page.locator('text=España').first.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass
    return browser, context, page


async def listar_urls_async(page, max_items: int) -> list[str]:
    """Pagina o catálogo coletando URLs (igual sources.vinted.listar_urls_items mas async)."""
    seen = set()
    base_url = page.url.split("&page=")[0]
    num_pagina = 1
    while len(seen) < max_items:
        if num_pagina > 1:
            url_pagina = f"{base_url}&page={num_pagina}"
            await page.goto(url_pagina, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
        urls = await page.evaluate("""() => {
            const seen = new Set();
            return Array.from(document.querySelectorAll('a[href*="/items/"]'))
                .map(a => a.href.split('?')[0])
                .filter(u => { if (seen.has(u)) return false; seen.add(u); return true; });
        }""")
        if not urls:
            break
        antes = len(seen)
        seen.update(urls)
        print(f"    página {num_pagina}: {len(urls)} itens (+{len(seen) - antes} novos, total {len(seen)})")
        if len(seen) >= max_items:
            break
        tem_proxima = await page.evaluate("""() => {
            return !!document.querySelector('a[aria-label="Next"], [data-testid="pagination-next"], nav a[href*="page="]');
        }""")
        if not tem_proxima:
            break
        num_pagina += 1
    return list(seen)[:max_items]


async def worker(tab, queue: asyncio.Queue, resultados: dict, total: int, lock: asyncio.Lock):
    """Worker que pega URLs da fila e processa numa tab própria."""
    while True:
        try:
            i, url = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            item = await extract_item_async(tab, url)
            async with lock:
                resultados[i] = item
                n = len(resultados)
                print(f"    [{n}/{total}] {item.get('titulo','')[:50]} — {item.get('preco')} · {item.get('tamanho')}")
        except Exception as e:
            async with lock:
                resultados[i] = {"url": url, "erro": str(e)}
                print(f"    [erro] {url}: {str(e)[:80]}")
        finally:
            queue.task_done()


async def main_async():
    DATA.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    print("=== Didi · radar Sundek (Vinted) — modo async ===\n")
    t0 = time.time()

    async with async_playwright() as p:
        print("[1] Abrindo sessão (vinted.pt → Espanha → cookies)")
        browser, context, page = await abrir_sessao(p)

        url = montar_url_sundek_hombre()
        print(f"[2] Catálogo filtrado:\n    {url}")
        await page.goto(url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        try:
            if await page.locator('text="Where do you live?"').is_visible(timeout=2000):
                await page.locator('text=España').first.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        print(f"[3] Listando até {MAX_ITEMS_POR_RODADA} URLs de items...")
        urls = await listar_urls_async(page, MAX_ITEMS_POR_RODADA)
        print(f"    {len(urls)} URLs.\n")

        print(f"[4] Extraindo dados ({WORKERS} tabs em paralelo)")
        # Cria N tabs no mesmo contexto (compartilham sessão)
        tabs = [page] + [await context.new_page() for _ in range(WORKERS - 1)]
        queue: asyncio.Queue = asyncio.Queue()
        for i, u in enumerate(urls):
            queue.put_nowait((i, u))
        resultados: dict = {}
        lock = asyncio.Lock()
        workers = [asyncio.create_task(worker(tab, queue, resultados, len(urls), lock)) for tab in tabs]
        await queue.join()
        for w in workers:
            w.cancel()

        coletados = [resultados[k] for k in sorted(resultados)]
        out = DATA / "coleta.json"
        out.write_text(json.dumps(coletados, indent=2, ensure_ascii=False))
        print(f"\n[5] {len(coletados)} itens salvos em data/coleta.json")

        stats = atualizar_com_scrape(coletados)
        print(f"\n[6] Histórico:")
        print(f"    novos:           {stats['novos']}")
        print(f"    ainda listados:  {stats['ainda_listados']}")
        print(f"    baixaram preço:  {stats['preco_baixou']}")
        print(f"    vendidos agora:  {stats['vendidos_agora']}")
        print(f"    total tracking:  {stats['total_historico']}")
        print(f"\n    duração total: {time.time() - t0:.1f}s")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main_async())
