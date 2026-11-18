"""Source: Vinted (vinted.es e vinted.co.uk) — filtrado para Vilebrequin."""
from ..config import VILEBREQUIN, VINTED
from .vinted import faixa_de_preco


def montar_url_ville_hombre(base_url: str | None = None, moeda: str = "EUR") -> str:
    base = f'{base_url or VINTED["es_base_url"]}/catalog'
    parts = ["search_text=vilebrequin"]

    if VILEBREQUIN.get("brand_id_vinted"):
        parts.append(f"brand_ids[]={VILEBREQUIN['brand_id_vinted']}")

    parts.append(f"catalog_ids[]={VINTED['catalog_id_banho_hombre']}")

    for sid in VILEBREQUIN["size_ids_vinted"].values():
        parts.append(f"size_ids[]={sid}")

    for st in VILEBREQUIN["status_ids_vinted"].values():
        parts.append(f"status_ids[]={st}")

    p_min, p_max = faixa_de_preco(VILEBREQUIN["preco_min"], VILEBREQUIN["preco_max"], moeda)
    parts += [
        f"price_from={p_min}",
        f"price_to={p_max}",
        f"currency={moeda}",
        "order=newest_first",
    ]
    return f"{base}?{'&'.join(parts)}"
