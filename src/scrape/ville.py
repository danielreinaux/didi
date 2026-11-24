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
from ..config import MAX_ITEMS_POR_RODADA, TETO_ANUNCIO_S, VINTED_UK
from . import vigia
from .extract import extract_item
from .guard import checar_fotos
from ..sources.vinted import listar_urls_items
from ..sources.vinted_ville import montar_url_ville_hombre
from ..sources import vinted_uk

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
        marca_nav = vigia.nova_marca()
        browser, _, page = abrir_sessao_vinted(p, marca_nav)

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
            # Teto por anúncio (scrape/vigia.py), como no Sundek.
            with vigia.Teto(TETO_ANUNCIO_S, marca_nav) as teto:
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

            if teto.estourou:
                print(f"        TRAVOU: passou de {TETO_ANUNCIO_S} s neste anúncio; navegador fechado à força "
                      "(o anúncio entra na rodada seguinte). Reabrindo o navegador.")
                try:
                    marca_nav = vigia.nova_marca()
                    browser, _, page = abrir_sessao_vinted(p, marca_nav)
                except Exception as e:  # noqa: BLE001
                    print(f"        não reabriu ({str(e)[:120]}) — fim da coleta desta rodada")
                    break

            if (i + 1) % 20 == 0:
                out.write_text(json.dumps(coletados, indent=2, ensure_ascii=False), encoding="utf-8")

        out.write_text(json.dumps(coletados, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[5] {len(coletados)} itens salvos em data/coleta-ville.json")

        # [5b] Vinted UK: só os anúncios ainda não vistos, depois da Espanha (sources/vinted_uk.py).
        #      Ficam fora do guard abaixo, que continua só com a Espanha.
        if VINTED_UK:
            uk = vinted_uk.coletar(browser, montar_url_ville_hombre(vinted_uk.BASE_URL, vinted_uk.MOEDA),
                                   DATA / "coleta-ville-classificada.json", {c.get("id") for c in coletados},
                                   marca_nav=marca_nav)
            if uk:
                out.write_text(json.dumps(coletados + uk, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"    {len(coletados) + len(uk)} itens em data/coleta-ville.json ({len(uk)} do UK)")
        # Guard-rail: se a extração de fotos quebrou, falha o step (ver guard.py).
        # Vem DEPOIS do save (e do histórico) pra não perder o que já foi coletado.
        checar_fotos(coletados, "ville")

        print(f"\n    duração total: {time.time() - t0:.1f}s")

        try:
            browser.close()
        except Exception:  # noqa: BLE001 — navegador já fechado à força pelo teto
            pass


if __name__ == "__main__":
    main()
