"""Source: Vinted (vinted.es). Monta URL filtrada e lista URLs de items."""
from urllib.parse import urlencode

from ..config import SUNDEK, VINTED


def montar_url_sundek_hombre() -> str:
    # Vinted exige parâmetros repetidos para múltiplos valores (não vírgula)
    base = f'{VINTED["es_base_url"]}/catalog'
    parts = [
        "search_text=sundek",
        f"brand_ids[]={SUNDEK['brand_id_vinted']}",
        f"catalog_ids[]={VINTED['catalog_id_hombre']}",
    ]
    for sid in SUNDEK["size_ids_vinted"].values():
        parts.append(f"size_ids[]={sid}")
    for st in SUNDEK["status_ids_vinted"].values():
        parts.append(f"status_ids[]={st}")
    parts += [
        f"price_from={SUNDEK['preco_min']}",
        f"price_to={SUNDEK['preco_max']}",
        "currency=EUR",
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
