"""Filtros de busca e configuração da IA. Derivados do manual de regras."""

# ---------- Sundek ----------
SUNDEK = {
    "marca": "Sundek",
    "brand_id_vinted": 36501,
    "preco_min": 1,
    "preco_max": 45,           # €. Acima disso é zona de barganha.
    # Tamanhos aceitos (texto extraído da página). Inclui literais e numéricos.
    "tamanhos_aceitos": ["S", "M", "L", "XL", "29", "30", "31", "32", "33", "34"],
    # Sem filtro de size na URL — filtramos por texto no prefilter após extração.
    # Isso captura tamanhos numéricos (W29, W31...) que o Vinted não expõe por ID simples.
    "size_ids_vinted": {},
    "status_ids_vinted": {
        "nuevo_con_etiquetas": 6,
        "nuevo_sin_etiquetas": 1,
        "muy_bueno": 2,
        "bueno": 3,
    },
}

# ---------- Vilebrequin ----------
VILEBREQUIN = {
    "marca": "Vilebrequin",
    "brand_id_vinted": None,    # descobrir depois
    "preco_min": 40,
    "preco_max": 100,
    "tamanhos_aceitos": ["S", "M", "L", "XL"],
    "size_ids_vinted": {"S": 207, "M": 208, "L": 209, "XL": 210},
    "status_ids_vinted": {
        "nuevo_con_etiquetas": 6,
        "nuevo_sin_etiquetas": 1,
        "muy_bueno": 2,
    },
}

# ---------- Vinted ----------
VINTED = {
    "home_url": "https://www.vinted.pt",
    "es_base_url": "https://www.vinted.es",
    "catalog_id_hombre": 5,
}

# Quantos itens a coleta deve trazer por execução (por marca).
MAX_ITEMS_POR_RODADA = 900

# Modelo de IA pra classificação visual.
IA = {
    "provider": "openai",
    "model": "gpt-4o-mini",      # padrão: liso/estampado, brand check, cor
    "model_detalhes": "gpt-4o",  # visão fina: elástico e etiqueta
}
