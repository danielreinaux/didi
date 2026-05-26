"""Coleta de Vilebrequin no Vinted.

Uso:
    python -m src.scrape_ville                  # browser visível
    HEADLESS=true python -m src.scrape_ville    # silencioso
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..utils.browser import abrir_sessao_vinted
from ..config import MAX_ITEMS_POR_RODADA
from .extract import extract_item
from ..sources.vinted import listar_urls_items
from ..sources.vinted_ville import montar_url_ville_hombre

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
SHOTS = DATA / "screenshots"


def main() -> None:
    DATA.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)

    print("=== Didi · radar Vilebrequin (Vinted) ===\n")
    t0 = time.time()

    with sync_playwright() as p:
        print("[1] Abrindo sessão (vinted.pt → Espanha → cookies)")
        browser, _, page = abrir_sessao_vinted(p)

        url = montar_url_ville_hombre()
        print(f"[2] Catálogo filtrado:\n    {url}")
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2500)

        try:
            if page.locator('text="Where do you live?"').is_visible(timeout=2000):
                page.locator('text=España').first.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        page.screenshot(path=str(SHOTS / "00-catalogo-ville.png"))

        print(f"[3] Listando até {MAX_ITEMS_POR_RODADA} URLs de items...")
        urls = listar_urls_items(page, MAX_ITEMS_POR_RODADA)
        print(f"    {len(urls)} URLs.\n")

        print("[4] Extraindo dados de cada item")
        out = DATA / "coleta-ville.json"
        coletados = []

        for i, u in enumerate(urls):
            idx = f"{i + 1:02d}"
            print(f"    [{i + 1}/{len(urls)}] {u}")
            try:
                item = extract_item(page, u)
                page.screenshot(path=str(SHOTS / f"ville-{idx}.png"))
                print(
                    f"        {item['titulo']} — {item['preco']} · "
                    f"{item['tamanho']} · {item['estado']} · {item['cor']}"
                )
                coletados.append(item)
            except Exception as e:
                msg = str(e)[:120]
                print(f"        ERRO: {msg}")
                coletados.append({"url": u, "erro": str(e)})

            if (i + 1) % 20 == 0:
                out.write_text(json.dumps(coletados, indent=2, ensure_ascii=False))

        out.write_text(json.dumps(coletados, indent=2, ensure_ascii=False))
        print(f"\n[5] {len(coletados)} itens salvos em data/coleta-ville.json")
        print(f"\n    duração total: {time.time() - t0:.1f}s")

        browser.close()


if __name__ == "__main__":
    main()
