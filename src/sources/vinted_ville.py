"""Source: Vinted (vinted.es) — filtrado para Vilebrequin."""
from ..config import VILEBREQUIN, VINTED


def montar_url_ville_hombre() -> str:
    base = f'{VINTED["es_base_url"]}/catalog'
    parts = ["search_text=vilebrequin"]

    if VILEBREQUIN.get("brand_id_vinted"):
        parts.append(f"brand_ids[]={VILEBREQUIN['brand_id_vinted']}")

    parts.append(f"catalog_ids[]={VINTED['catalog_id_banho_hombre']}")

    for sid in VILEBREQUIN["size_ids_vinted"].values():
        parts.append(f"size_ids[]={sid}")

    for st in VILEBREQUIN["status_ids_vinted"].values():
        parts.append(f"status_ids[]={st}")

    parts += [
        f"price_from={VILEBREQUIN['preco_min']}",
        f"price_to={VILEBREQUIN['preco_max']}",
        "currency=EUR",
        "order=newest_first",
    ]
    return f"{base}?{'&'.join(parts)}"
