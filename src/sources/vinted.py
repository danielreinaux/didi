"""Source: Vinted (vinted.es e vinted.co.uk). Monta URL filtrada e lista URLs de items."""
import math
from urllib.parse import urlencode

from ..config import GBP_EUR, SUNDEK, VINTED


def faixa_de_preco(preco_min: float, preco_max: float, moeda: str) -> tuple[int, int]:
    """Faixa de preço do filtro na moeda do site. Os limites da config são em euro; no UK
    viram libra pela cotação, arredondando para fora (o score refaz a conta em euro)."""
    if moeda == "EUR":
        return int(preco_min), int(preco_max)
    return max(1, math.floor(preco_min / GBP_EUR)), math.ceil(preco_max / GBP_EUR)


def montar_url_sundek_hombre(base_url: str | None = None, moeda: str = "EUR") -> str:
    # Vinted exige parâmetros repetidos para múltiplos valores (não vírgula)
    base = f'{base_url or VINTED["es_base_url"]}/catalog'
    parts = [
        "search_text=sundek",
        f"brand_ids[]={SUNDEK['brand_id_vinted']}",
        f"catalog_ids[]={VINTED['catalog_id_hombre']}",
    ]
    for sid in SUNDEK["size_ids_vinted"].values():
        parts.append(f"size_ids[]={sid}")
    for st in SUNDEK["status_ids_vinted"].values():
        parts.append(f"status_ids[]={st}")
    p_min, p_max = faixa_de_preco(SUNDEK["preco_min"], SUNDEK["preco_max"], moeda)
    parts += [
        f"price_from={p_min}",
        f"price_to={p_max}",
        f"currency={moeda}",
        "order=newest_first",
    ]
    return f"{base}?{'&'.join(parts)}"


def _extrair_urls_pagina(page) -> list[str]:
    """Links da grade da busca, na ordem do catálogo (mais novos primeiro). Fica de fora o
    "armário em destaque" (data-testid closet-promotion-*): propaganda paga de um vendedor,
    de qualquer marca — 60 links a mais na página, que entravam no lugar dos anúncios novos."""
    return page.evaluate("""() => {
        const seen = new Set();
        return Array.from(document.querySelectorAll('a[href*="/items/"]'))
            .filter(a => !a.closest('[data-testid^="closet-promotion"]'))
            .map(a => a.href.split('?')[0])
            .filter(u => { if (seen.has(u)) return false; seen.add(u); return true; });
    }""")


def listar_urls_items(page, max_items: int = 20) -> list[str]:
    """Navega pelas páginas do catálogo até ter max_items URLs ou não haver mais páginas."""
    seen: dict[str, None] = {}  # dict, não set: mantém a ordem do catálogo (02/11/2026)
    base_url = page.url.split("&page=")[0]
    num_pagina = 1

    while len(seen) < max_items:
        url_pagina = base_url if num_pagina == 1 else f"{base_url}&page={num_pagina}"
        if num_pagina > 1:
            page.goto(url_pagina, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

        urls = _extrair_urls_pagina(page)
        if not urls:
            break

        antes = len(seen)
        seen.update(dict.fromkeys(urls))
        print(f"    página {num_pagina}: {len(urls)} itens (+{len(seen) - antes} novos, total {len(seen)})")

        if len(seen) >= max_items:
            break

        # verificar se existe próxima página
        tem_proxima = page.evaluate("""() => {
            return !!document.querySelector('a[aria-label="Next"], [data-testid="pagination-next"], nav a[href*="page="]');
        }""")
        if not tem_proxima:
            break

        num_pagina += 1

    return list(seen)[:max_items]
