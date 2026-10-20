"""Filtros de busca e configuração da IA. Derivados do manual de regras."""

# Vilebrequin DESLIGADA em 20/10/2026 — foco 100% na Sundek. O código e os dados da Ville
# continuam no repo; para religar: True aqui + tirar o `if: false` do job `ville` no
# .github/workflows/scrape-cron.yml.
VILLE_ATIVA = False

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
    "brand_id_vinted": 99810,
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
    "catalog_id_banho_hombre": 2050,
}

# Quantos itens a coleta deve trazer por execução (por marca).
# Override pontual via env MAX_ITEMS (ex: testar com 100 sem mexer no padrão).
import os as _os
MAX_ITEMS_POR_RODADA = int(_os.environ.get("MAX_ITEMS", "60"))

# Modelo de IA pra classificação visual.
IA = {
    "provider": "openai",
    "model": "gpt-4o-mini",      # padrão: liso/estampado, brand check, cor
    "model_detalhes": "gpt-4o",  # visão fina: elástico e etiqueta
}

# Listra Sundek — faixa de UMA cor só conta como listra?
#   "conta"     = regra de jun/2026 (o prompt v3 sozinho).
#   "nao_conta" = decisão do CLIENTE (out/2026): faixa de UMA cor só na COSTURA LATERAL
#                 (ou viés na borda da perna) NÃO é listra. Quando o v3 diz "listra" com
#                 ≤1 cor, uma 2ª olhada (gpt-4o, detail high, prompts/listra_confirma.py)
#                 conta as cores e diz onde a faixa está; 1 cor + lateral/borda → sem listra.
#                 Arco nas costas de 1 cor continua contando (fora da decisão do cliente).
#                 Em produção (run.py) a 2ª olhada só roda em item ATIVO que iria PASSAR
#                 (≈ US$ 0,0095 cada; 1ª rodada ≈ 34 itens ≈ US$ 0,32; depois < US$ 1/mês).
#   Env LISTRA_FAIXA_UNICA sobrepõe (medição; o harness do gabarito confere todo disparado).
LISTRA_FAIXA_UNICA = "nao_conta"  # decidido pelo cliente em 20/10/2026
