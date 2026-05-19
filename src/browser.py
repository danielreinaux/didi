"""Setup do Playwright: abre browser, vai pra Vinted PT, seleciona Espanha,
aceita cookies. Retorna (browser, context, page) prontos pra uso.
"""
import os
from playwright.sync_api import sync_playwright

from .config import VINTED

HEADLESS = os.environ.get("HEADLESS", "").lower() == "true"


def abrir_sessao_vinted(playwright):
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        slow_mo=0 if HEADLESS else 60,
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="es-ES",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()

    # 1. abre vinted.pt
    page.goto(VINTED["home_url"], wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    # 2. seleciona Espanha (modal de país)
    try:
        esp = page.locator('a:has-text("Espanha"), a[href*="vinted.es"]').first
        if esp.is_visible(timeout=4000):
            esp.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
    except Exception:
        pass

    # 3. aceita cookies
    for sel in [
        "#onetrust-accept-btn-handler",
        'button:has-text("Aceptar")',
        'button:has-text("Accept all")',
    ]:
        try:
            b = page.locator(sel).first
            if b.is_visible(timeout=1500):
                b.click()
                page.wait_for_timeout(500)
                break
        except Exception:
            pass
    page.wait_for_timeout(500)

    # 4. fechar modal "Where do you live?" se reaparecer no vinted.es
    try:
        modal = page.locator('[data-testid="country-select-modal"], [role="dialog"]:has-text("Where do you live")')
        if modal.is_visible(timeout=2000):
            page.locator('text=España').first.click()
            page.wait_for_timeout(1000)
    except Exception:
        pass

    return browser, context, page
