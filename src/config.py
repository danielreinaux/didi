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
    # 2º olhar do "desbotado" (só nos lisos que o tipo marcou desbotado) — rota sundek:desbotado.
    "model_desbotado": "anthropic/claude-haiku-5.5",
    "desbotado_votos": 3,
}

# Roteamento POR AGENTE (src/utils/llm.py). gpt-4o e gpt-4o-mini saem da API da OpenAI em
# 14/01/2027; estes substitutos empataram com a produção no gabarito (2 datasets, base prod20out,
# bench modelos2 out/2026: acerto por critério + decisão falso descarte/falsa passagem).
# Só entram em vigor com o secret OPENROUTER_API_KEY; sem ele (ou com IA_ROTAS_DESLIGADAS=1)
# tudo segue na OpenAI como antes. Se o OpenRouter falhar, a chamada cai no modelo legado.
# Agente sem rota aqui = OpenAI: cor (todos os substitutos leem o azul claro como médio →
# precisa recalibrar o prompt antes de trocar) e marca_recheck/listra_confirma/velcro (raros,
# ainda não medidos fora do gpt-4o).
# Opções lidas pelos módulos (não vão para a API): "colagem" (marca), "max_fotos" (tipo/cor).
_SEM_RACIOCINIO = {"reasoning": {"enabled": False}, "min_tokens": 2500}
_GEMINI3 = {"reasoning": {"effort": "minimal"}, "min_tokens": 3000}
IA_ROTAS = {
    # marca: idêntico à produção em 2 rodadas (0 itens mudados), US$0,00019/chamada (mini: 0,0018)
    # colagem DESLIGADA nesta rota: no flash-lite cada foto custa ~258 tokens (não 2.833) e a
    # colagem baixou e_sundek de 91/92 para 89/92 no gabarito (21/10).
    "sundek:marca": {"to": "openrouter:google/gemini-2.5-flash-lite", **_SEM_RACIOCINIO, "colagem": False,
                     "reserva": {"to": "openrouter:bytedance-seed/seed-2.0-mini", **_SEM_RACIOCINIO}},
    # tipo: +2/+1/0 em 3 rodadas, corrige 1 falso descarte (9280328167). Fixado no host CoreWeave
    # (bf16): no OpenRouter o gemma-4 só tem hosts de terceiros, e o Google Vertex deu erro 400 em
    # 25/93 itens. US$0,00022 (mini: 0,0019)
    # tipo: DESLIGADO em 21/10 (volta ao gpt-4o-mini). O gemma-4 marca listra_na_frente=true em
    # short com listra só na LATERAL (a própria justificativa diz "listras laterais"): 24 de ~55
    # aprovados do app viraram descarte na reclassificação. O gabarito não pegou. Não religar sem
    # medir listra_na_frente nos aprovados do app.
    # "sundek:tipo": {"to": "openrouter:google/gemma-4-26b-a4b-it", **_SEM_RACIOCINIO,
    #                 "provider": {"order": ["coreweave"], "allow_fallbacks": False},
    #                 "reserva": {"to": "openrouter:google/gemma-4-26b-a4b-it", **_SEM_RACIOCINIO}},
    # 2º olhar do desbotado (só nos lisos marcados desbotado; 3 votos) — Claude Haiku 5.5.
    # Sem a chave → não roda e vale o desbotado do tipo. Medição: reports/tipo_sundek.md.
    "sundek:desbotado": {"to": "openrouter:anthropic/claude-haiku-5.5", "min_tokens": 1500},
    # listra v3: +1 critério nas 2 rodadas, decisão igual; US$0,00065 (mini: 0,0023)
    "sundek:listra": {"to": "openrouter:bytedance-seed/seed-2.0-mini", **_SEM_RACIOCINIO,
                      # reserva +2 no gabarito, mas o Google tira o 3.1-flash-lite em 05/2027
                      "reserva": {"to": "openrouter:google/gemini-3.1-flash-lite", **_GEMINI3}},
    # elástico: DESLIGADO em 22/10 (volta ao gpt-4o, com o prompt v3). O seed-2.0-lite via
    # "franzido de elástico" em boardshort clássico de cós reto (3 de 3 apontados pelo Daniel no
    # app); com o prompt v3: gabarito sim 55/55 nos dois, não 21/23 (seed) × 22/23 (4o), os 3
    # do Daniel 1/3 × 3/3, fechamento 72/78 × 74/78. Achar substituto vigente antes de 14/01/2027.
    # # elástico (prompt sem CoT): critério −2/−1/0 em 3 rodadas; decisão igual exceto 1 falsa passagem
    # # sistemática (9279834011, ver relatório). US$0,0016 (4o: ~0,006 faturado / 0,011 lista)
    # # (sem reserva: o gemini-3.5-flash-lite, −2 com o prompt antigo, desaba no prompt sem CoT:
    # #  −11 e +4 falsas passagens no gabarito, 21/10)
    # "sundek:elastico": {"to": "openrouter:bytedance-seed/seed-2.0-lite", **_SEM_RACIOCINIO},
    # botão (localizador + detector): 19/21 votos "botão" do cliente (4o: 17/21), 0/35 FP;
    # gabarito 2/2, 0/56 FP. US$0,0022/item (4o: ~0,0105)
    "sundek:crop_fly": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3,
                        "reserva": {"to": "openrouter:google/gemma-4-31b-it", **_SEM_RACIOCINIO}},
    "sundek:botao": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3,
                     "reserva": {"to": "openrouter:google/gemma-4-31b-it", **_SEM_RACIOCINIO}},
    # bolso (localizador do patch + leitura): Δ0, decisão igual; US$0,0026/item (4o: ~0,011)
    "sundek:crop_patch": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3},
    "sundek:bolso": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3},
    # etiqueta: Δ0, decisão igual; US$0,0001 (mini: 0,0016)
    "sundek:etiqueta": {"to": "openrouter:qwen/qwen3.7-flash", **_SEM_RACIOCINIO},
}

# Modelo da OpenAI por agente, para agente SEM rota no OpenRouter (src/utils/llm.py).
# Na família gpt-5/6 o llm.py ajusta os parâmetros; effort = reasoning_effort; detail força o
# detail das fotos. Agente fora daqui usa o `model` que o módulo passa (gpt-4o / gpt-4o-mini).
IA_OPENAI = {
    # elástico (27/10/2026): gpt-6.1-sol em high + raciocínio médio. No gabarito empata com o
    # gpt-4o (com elástico 55/55, sem 25/26), mas acerta boardshorts clássicos que o 4o ainda
    # lia "com elástico" no app (Daniel: 10533955620 branco, 9680308686 azul). Não sai da API em
    # 14/01/2027. ~US$ 0,016/item (gpt-4o ~0,006). Em low ou com raciocínio baixo perde 6 "com".
    "sundek:elastico": {"model": "gpt-6.1-sol", "detail": "high", "effort": "medium"},
}

# App (items.json) e e-mail só com anúncios RECENTES (Daniel, 26/10/2026): os 12 do e-mail de
# 21/10/2026 15:50 BRT + o que apareceu pela 1ª vez depois dele. O acervo antigo continua
# classificado (e no /history), só não aparece no app nem é avisado de novo — o ledger de
# notificados esquece depois de 30 dias e reenviava anúncio de julho/setembro como "novo".
APP_DESDE = "2026-10-21T18:50:00+00:00"
APP_TAMBEM_IDS = {
    "10434663113", "10429799119", "10435012306", "10472979058", "10438420408", "10434556060",
    "10468818456", "10467275521", "10381859411", "10433650344", "10454531920", "10441774590",
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
