"""Extrai dados estruturados da página de detalhe de um item Vinted."""
import re
from datetime import datetime, timezone


def _strip_label(text: str | None, labels: list[str]) -> str | None:
    if not text:
        return None
    t = text.strip()
    for lbl in labels:
        if t.startswith(lbl):
            return t[len(lbl):].strip()
    return t


def extract_item(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    page.wait_for_timeout(1200)

    raw = page.evaluate("""() => {
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

      const fotos = Array.from(document.querySelectorAll('img'))
        .map(img => img.src)
        .filter(u => u.includes('vinted.net') && /\\/f\\d+\\//.test(u));

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
