"""Filtros de busca e configuração da IA. Derivados do manual de regras."""

# Vilebrequin desligada em 20/10/2026 (foco 100% na Sundek), religada em 05/11/2026 só no app
# (modo sombra) e com o E-MAIL LIGADO em 13/11/2026: as ofertas novas dela vão no mesmo e-mail do
# Sundek, numa seção própria. Com VILLE_EMAIL = False ela volta à sombra: fica no app e os
# candidatos entram no registro de avisados sem envio (por isso ligar não mandou o acumulado).
# Para desligar tudo: VILLE_ATIVA = False + `if: false` no job `ville` do workflow.
VILLE_ATIVA = True
VILLE_EMAIL = True
# No app, só os anúncios da Ville vistos pela 1ª vez depois da volta (o acervo de set–out/2026
# está quase todo vendido e foi classificado com as regras antigas).
VILLE_APP_DESDE = "2026-11-05T00:00:00+00:00"

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
    # Piso era €40 (a "faixa esperada" do manual), mas a regra de compra do cliente diz
    # tartaruga grande < €40 → comprável sempre, e liso/tartaruga pequena ótimo a €25: a
    # busca nunca trazia justamente os mais baratos (08/11/2026).
    "preco_min": 1,
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
    # Ville (gabarito ville + compráveis ville, 77 itens com resposta, 30/10/2026; 8 fotos em high):
    # cordão: gpt-4o-mini low/4 fotos 78% (achava 2 de 11 cordões CINZA = coleção antiga) →
    # Gemini 3.5 Flash-Lite 94% nas 2 rodadas (10 de 11 cinzas), US$0,0017/item (mini: 0,0015).
    # Haiku 5.5 deu 91–92% (reserva). gpt-6.1-sol 95% a US$0,0096.
    "ville:cordao": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3,
                     "reserva": {"to": "openrouter:anthropic/claude-haiku-5.5", "min_tokens": 1500}},
    # fecho: gpt-4o low/4 fotos 83% (6 cordões e 4 fivelas viravam "indefinido") → Gemini 3.5
    # Flash-Lite 92%, US$0,0015/item (4o: 0,0037). O erro que sobra é fivela↔botão (os dois excluem).
    "ville:fecho": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3,
                    "reserva": {"to": "openrouter:anthropic/claude-haiku-5.5", "min_tokens": 1500}},
    # cor de fundo da Ville: o principal fica no gpt-4o-mini (sem rota = OpenAI; com o prompt
    # cor_fundo_ville deu 91% vs 84–89% dos outros). Quando ele diz "branco", o Haiku 5.5 confere
    # (classify/cor_fundo_ville.py): o mini lia azul claríssimo como branco.
    "ville:cor_fundo_branco": {"to": "openrouter:anthropic/claude-haiku-5.5", "min_tokens": 1500},
    # Os agentes do Sundek que eram da OpenAI, agora pelo OpenRouter com o MESMO modelo e o mesmo
    # preço (05/11/2026): a chave da OpenAI foi invalidada em 04/11 (401 em toda chamada, nada
    # classificado desde 07:00 BRT). Daniel: "jogar as mesmas chaves que usamos na openai, só que
    # na openrouter". elástico/premiado repetem o IA_OPENAI (fotos em high, raciocínio médio).
    "sundek:tipo": "openrouter:openai/gpt-4o-mini",
    "sundek:cor": "openrouter:openai/gpt-4o-mini",
    "sundek:marca_recheck": "openrouter:openai/gpt-4o",
    "sundek:listra_confirma": "openrouter:openai/gpt-4o",
    "sundek:velcro": "openrouter:openai/gpt-4o",
    "sundek:elastico": {"to": "openrouter:openai/gpt-6.1-sol", "detail": "high",
                        "reasoning": {"effort": "medium"}, "min_tokens": 8000},
    "sundek:premiado": {"to": "openrouter:openai/gpt-6.1-sol", "detail": "high",
                        "reasoning": {"effort": "medium"}, "min_tokens": 8000},
    # Mesma troca na Ville (05/11/2026, antes de religar): padrão/tartaruga e marca (gpt-4o),
    # cor de fundo (gpt-4o-mini) e autenticidade (gpt-6.1-sol, como no IA_OPENAI).
    "ville:tartaruga": "openrouter:openai/gpt-4o",
    "ville:marca": "openrouter:openai/gpt-4o",
    "ville:cor_fundo": "openrouter:openai/gpt-4o-mini",
    # 12/11/2026: raciocínio médio (era baixo) — em baixo não via tartaruga cortada no contorno
    # do bolso ou inventava corte em original; ver prompts/autenticidade_ville_v2.py.
    "ville:autenticidade": {"to": "openrouter:openai/gpt-6.1-sol", "detail": "high",
                            "reasoning": {"effort": "medium"}, "min_tokens": 8000},
    # Estado da Ville (desbotado + mancha → aviso), só nos candidatos: Haiku 3 votos + Gemini.
    # Bancada 05/11/2026 em classify/estado_ville.py.
    "ville:estado": {"to": "openrouter:anthropic/claude-haiku-5.5", "detail": "high", "min_tokens": 1500},
    "ville:estado_forte": {"to": "openrouter:google/gemini-3.5-flash-lite", "detail": "high", **_GEMINI3},
    # Fotos para os agentes (classify/orientacao.py, 13–14/11/2026), Sundek e Ville, depois da
    # marca. Chamada do LADO: de que lado está o cós, para pôr em pé a foto de cabeça para baixo
    # ou deitada (122 fotos de 31 anúncios reais: 16 giradas, as 16 certas). Chamada da VISTA, só
    # em anúncio com mais de 5 fotos: acha a foto das costas quando ela vem no fim do anúncio
    # (14 anúncios reais conferidos no olho, 2 precisavam e os 2 saíram certos). O
    # gemini-2.5-flash-lite (4x mais barato) errou o lado em várias fotos deitadas.
    # ~US$ 0,001 por anúncio de até 5 fotos; ~US$ 0,003 nos de mais de 5. Sem esta rota, as
    # fotos vão como vieram.
    "orientacao": {"to": "openrouter:google/gemini-3.5-flash-lite", **_GEMINI3},
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
    # short premiado (28/10/2026): compara as fotos com os 3 modelos favoritos do cliente. Só
    # roda em comprável com elástico e corpo escuro (poucos por dia). ~US$ 0,012/item (medido).
    "sundek:premiado": {"model": "gpt-6.1-sol", "detail": "high", "effort": "medium"},
    # autenticidade da Ville v2 (02/11/2026): critério do comprador (bolso "completa"?, estampado sem
    # bolso, etiquetinha clonada) com as fotos inteiras. Bancada 79 itens: 5/7 falsos, 0/53
    # originais acusados (gpt-4o: 7/7 mas acusa 14/53; Gemini 4/7; Haiku 0/7). ~US$0,008/item.
    # 12/11/2026: critério do contorno do bolso + raciocínio médio. Gabarito + 1 falso novo, 60
    # peças: 6/6 falsos, 54/54 originais (antes 4/6 e 52/54). ~US$0,009/item (medido).
    "ville:autenticidade": {"model": "gpt-6.1-sol", "detail": "high", "effort": "medium"},
}

# Short premiado (classify/premiado.py): preço do ANÚNCIO (sem a taxa) até este valor →
# "🚨 COMPRA URGENTE" no e-mail e no app; acima → "⭐ short premiado disponível".
# Cliente (27/10/2026): "15 ou 20 euros" — €20 porque o teto desses shorts fica perto de €40 e
# o premiado de €20 de 27/10 vendeu em minutos.
PREMIADO_URGENTE_ATE = 20.0

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

# Correções manuais da classificação, por anúncio: a IA errou um campo e o certo foi conferido
# por uma pessoa. classify/run.py aplica antes de recalcular o score em toda rodada.
CORRECOES_MANUAIS = {
    # 03/11/2026 (Daniel): meia-lua PRETA com o sol em traço neon e etiqueta "Made in the
    # U.S.A." = coleção antiga, sem o nome SUNDEK. A IA leu o desenho neon como "patch fluo".
    "10649425793": {"bolso_traseiro_tem_nome": False,
                    "bolso_evidencia": "Patch preto com o sol em traço neon, sem o nome SUNDEK "
                                       "(coleção antiga) — corrigido à mão em 03/11/2026"},
}
