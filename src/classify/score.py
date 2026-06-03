"""Score 0-100 por item. Combina qualidade dos atributos + eficiência de preço.

Score = atributos (0~70) + eficiência de preço (0~30)
Resultado:
  >= 70 → comprável
  45~69 → médio (tenta barganha)
  < 45  → descartado
"""
import math
import re

# Tetos base por tier_final (€)
TETO_BASE = {
    "maravilhoso": 40,
    "muito_boa":   32,
    "boa":         25,
    "ok":          18,
    "ruim":         0,
}

# Modificadores de teto (€)
MOD_TAMANHO = {"M": +5, "L": 0, "XL": -3, "S": -5}
MOD_ELASTICO = {True: 0, False: -8}
MOD_ETIQUETA = {True: +4, False: 0}

# Pontos de atributo (máx 100)
PTS_TIER = {
    "maravilhoso": 30,
    "muito_boa":   22,
    "boa":         15,
    "ok":           8,
    "ruim":         0,
}
PTS_TAMANHO = {"M": 20, "L": 16, "XL": 8, "S": 4}
PTS_ELASTICO = 22    # com elástico — atributo forte (doc 1.2: padrão preferido)
PTS_SEM_ELASTICO = -15  # sem elástico — perde muita pontuação (doc 1.2)
PTS_ETIQUETA = 10    # hang-tag de papel visível na foto
PTS_LISTRA_SALVA = 5 # bônus quando listra salva a cor

# Exclusões automáticas (além de ruim/estampado/desbotado):
# bicolor, botao/velcro, tecido_brilhoso → descarte direto no bloco de exclusoes
# sem elástico + tamanho numérico fora de 31-34 → exclusão (doc 1.2)


def _parse_preco(preco_str: str | None) -> float | None:
    """'4,90 €' → 4.90"""
    if not preco_str:
        return None
    nums = re.findall(r"[\d,\.]+", preco_str)
    if not nums:
        return None
    try:
        return float(nums[0].replace(",", "."))
    except ValueError:
        return None


def _oferta_redonda(base: float) -> int:
    """Preço de oferta 'psicológico': maior múltiplo de 5 abaixo do preço base,
    com piso de 80% do base (não ofender em itens baratos).
    Ex: base 35 → 30 · 34 → 30 · 20 → 16 · 9 → 7."""
    alvo5 = math.floor((base - 0.01) / 5) * 5
    piso = round(base * 0.80)
    return max(int(alvo5), int(piso), 1)


def _negociacao(base: float | None, teto: float, ratio: float | None) -> dict:
    """Sugestão de como abordar o vendedor (oferta no Vinted é sobre o preço BASE).
    - preço já dentro do teto (ratio ≤ 1) → FECHAR: oferta concreta redonda.
    - preço acima do teto (ratio > 1, distante) → NEGOCIAR: pedir 'best price', alvo = teto.
    """
    if not base:
        return {}
    if ratio is not None and ratio <= 1.0:
        oferta = _oferta_redonda(base)
        return {
            "modo": "fechar",
            "oferta": oferta,
            "msg": f"💰 Oferecer €{oferta} — \"por {oferta} aceita?\". Se recusar, ainda vale o preço pedido.",
        }
    alvo = int(round(teto)) if teto else None
    return {
        "modo": "negociar",
        "oferta": alvo,
        "msg": (f"🗨️ Pedir desconto: \"What's your best price?\" — alvo ≤ €{alvo}."
                if alvo else "🗨️ Pedir: \"What's your best price?\""),
    }


def _preco_efetivo(item: dict) -> float | None:
    """Preço que o comprador REALMENTE paga = item + proteção ao comprador
    (campo 'preco_total' do Vinted, ex: 20,00 → 21,70). NÃO inclui frete.
    Trava de sanidade: o total só vale se ficar entre o base e ~base×1.4+€2
    (proteção é ~5% + €0.70); fora disso (ex: capturou frete) cai pro base."""
    base = _parse_preco(item.get("preco"))
    total = _parse_preco(item.get("preco_total"))
    if total is not None and base is not None:
        if base <= total <= base * 1.4 + 2:
            return total
        return base  # total suspeito (provável frete) → usa base
    return total if base is None else base


def _tamanho_key(tamanho: str | None) -> str:
    if not tamanho:
        return "L"
    t = (tamanho or "").strip().upper()
    for key in ("XXL", "XL", "M", "L", "S"):  # XXL antes de XL
        if key in t:
            return key
    # Numeric (31, 32, 33, 34 → L equivalent)
    if re.search(r"\b(29|30|31|32|33|34)\b", t):
        return "L"
    return "L"


def _tamanho_numerico(tamanho: str | None, titulo: str | None = None) -> int | None:
    """Retorna tamanho numérico se houver (campo tamanho OU título do anúncio)."""
    for txt in (tamanho, titulo):
        if not txt:
            continue
        m = re.search(r"\b(2[5-9]|3[0-9])\b", txt)
        if m:
            return int(m.group())
    return None


def calcular_teto(tier_final: str, tamanho: str, tem_elastico: bool, tem_etiqueta: bool) -> float:
    base = TETO_BASE.get(tier_final, 0)
    tam_key = _tamanho_key(tamanho)
    base += MOD_TAMANHO.get(tam_key, 0)
    base += MOD_ELASTICO.get(bool(tem_elastico), 0)
    base += MOD_ETIQUETA.get(bool(tem_etiqueta), 0)
    return max(base, 0)


def calcular_score(item: dict) -> dict:
    """Retorna dict com score, teto, decisao e breakdown."""
    cl = item.get("classificacao") or {}
    cor_raw = item.get("cor")
    cor = cor_raw if isinstance(cor_raw, dict) else {}
    elastico = item.get("elastico") or {}
    etiqueta = item.get("etiqueta") or {}

    tipo = cl.get("tipo")
    # cor só é avaliada nos 'liso'; nos demais (estampado/desbotado/tamanho/marca)
    # vem vazia. Distinguir os dois evita o carimbo fantasma de 'cor_ruim'.
    cor_avaliada = bool(cor.get("tier") or cor.get("tier_final"))
    tier_final = cor.get("tier_final") or cor.get("tier") or "ruim"
    tamanho = item.get("tamanho") or ""
    tam_key = _tamanho_key(tamanho)
    tem_elastico = elastico.get("tem_elastico") is True
    tipo_fechamento = elastico.get("tipo_fechamento") or ("elastico" if tem_elastico else "sem")
    # Ganha o bônus de etiqueta se a foto mostra a hang-tag OU o anúncio é
    # "Novo com etiqueta" (manual 1.7). Binário — sem escala de condição.
    _estado = (item.get("estado") or "").lower()
    _declarado_com_etiqueta = ("etiqueta" in _estado or "etichett" in _estado or "tag" in _estado) and \
        not ("sin " in _estado or "sem " in _estado or "without" in _estado or "senza" in _estado)
    tem_etiqueta = etiqueta.get("tem_etiqueta") is True or _declarado_com_etiqueta
    listra_salva = cor.get("listra_tier") == "salva"
    bicolor = cl.get("bicolor", False)
    tecido_brilhoso = cl.get("tecido_brilhoso", False)
    tem_bolso_frontal = cl.get("tem_bolso_frontal", False)
    listra_na_frente = cl.get("listra_na_frente", False)
    tem_bolso_traseiro = cl.get("tem_bolso_traseiro")  # None = indefinido (não exclui)

    # Item que FALHOU na classificação (ex: cota 429, rede) não é "descartado"
    # (não foi julgado) — é "não classificado": precisa reprocessar.
    if tipo == "erro":
        return {
            "score": 0,
            "teto": 0,
            "decisao": "nao_classificado",
            "motivo": "erro na classificação (cota/rede) — será reprocessado",
            "breakdown": {},
        }

    # Filtros de exclusão → score 0
    exclusoes = []
    if tipo in ("estampado", "logo_grande", "nao_sundek", "nao_short", "tamanho_invalido", "infantil"):
        exclusoes.append(tipo)
    if cl.get("aparencia") == "desbotado" or tipo == "desbotado":
        exclusoes.append("desbotado")
    if tier_final == "ruim" and cor_avaliada:
        # Distingue "a cor já é ruim" de "a cor era ok mas a COMBINAÇÃO com a
        # listra ficou ruim" (ex: listra rara/destoante derruba uma cor ok).
        _tier_raw = cor.get("tier")
        _motivo_combo = cor.get("combo_motivo") or ""
        if _tier_raw == "ruim" or "independente das listras" in _motivo_combo:
            exclusoes.append("cor_ruim")
        else:
            exclusoes.append("combinacao_listra_cor_ruim")
    if tecido_brilhoso:
        exclusoes.append("tecido_brilhoso")
    if bicolor:
        exclusoes.append("bicolor")
    if tipo_fechamento in ("botao", "velcro"):
        exclusoes.append(f"fechamento_{tipo_fechamento}")
    if tem_bolso_frontal:
        exclusoes.append("bolso_frontal")
    if listra_na_frente:
        exclusoes.append("listra_na_frente")
    if tem_bolso_traseiro is False:
        exclusoes.append("sem_bolso_traseiro")
    # Bolso traseiro só com logo (sem nome SUNDEK) = coleção antiga, exclui
    if tem_bolso_traseiro is True and cl.get("bolso_traseiro_tem_nome") is False:
        exclusoes.append("bolso_so_logo_colecao_antiga")
    if tipo == "liso" and cl.get("tem_listra_lateral_sundek") is False:
        exclusoes.append("sem_listra_sundek")
    # SEM elástico só vale em preto / branco / azul marinho (decisão do dono + feedback
    # do voto). Fora dessas cores → exclui. EXCEÇÃO: etiqueta visível (dá pra olhar).
    if not tem_elastico:
        _cn = (cor.get("cor_principal") or "").lower()
        _cor_elite = any(k in _cn for k in ("preto", "negro", "branco", "blanco", "marinho", "navy"))
        if not _cor_elite and not tem_etiqueta:
            exclusoes.append("sem_elastico_cor_fraca")
    # Piping: prompt dedicado detecta acabamento de costura disfarçado de listra
    if tipo == "liso" and cl.get("e_piping") is True:
        exclusoes.append("piping_nao_e_listra_sundek")
    if tam_key == "S" and tamanho.strip().upper().startswith("XS"):
        exclusoes.append("tamanho_XS")
    if tam_key == "XXL":
        exclusoes.append("tamanho_XXL")
    # Tamanho numérico fora de 31-34 = exclusão sempre (checa campo E título)
    num = _tamanho_numerico(tamanho, item.get("titulo"))
    if num is not None and not (31 <= num <= 34):
        exclusoes.append(f"tamanho_numerico_{num}")

    if exclusoes:
        return {
            "score": 0,
            "teto": 0,
            "decisao": "descartado",
            "motivo_exclusao": ", ".join(exclusoes),
            "breakdown": {},
        }

    # Parte 1 — Atributos
    pts_tier = PTS_TIER.get(tier_final, 0)
    pts_tam = PTS_TAMANHO.get(tam_key, 5)
    pts_el = PTS_ELASTICO if tem_elastico else PTS_SEM_ELASTICO
    pts_et = PTS_ETIQUETA if tem_etiqueta else 0
    pts_listra = PTS_LISTRA_SALVA if listra_salva else 0
    pts_atributos = max(0, pts_tier + pts_tam + pts_el + pts_et + pts_listra)

    # Parte 2 — Eficiência de preço (0~30)
    teto = calcular_teto(tier_final, tamanho, tem_elastico, tem_etiqueta)
    # Preço efetivo = item + proteção ao comprador (o que o comprador paga de fato).
    preco = _preco_efetivo(item)

    pts_preco = 0
    ratio = None
    if preco and teto > 0:
        ratio = preco / teto
        if ratio <= 0.50:
            pts_preco = 30
        elif ratio <= 0.70:
            pts_preco = 20
        elif ratio <= 0.90:
            pts_preco = 10
        elif ratio <= 1.00:
            pts_preco = 5
        else:
            pts_preco = 0

    score = min(100, pts_atributos + pts_preco)

    # Decisão
    if preco and teto > 0 and preco > teto * 1.25:
        decisao = "descartado"
        motivo = f"preço €{preco:.2f} acima do teto €{teto:.2f} × 1.25"
    elif score >= 70:
        decisao = "compravel"
        motivo = ""
    elif score >= 45:
        decisao = "medio"
        motivo = "tentar barganha"
    else:
        decisao = "descartado"
        motivo = "score baixo"

    # Override preço para elásticos: barato com elástico sempre vale olhar
    if tem_elastico and preco and tier_final != "ruim":
        if preco <= 9 and tier_final in ("boa", "muito_boa", "maravilhoso"):
            decisao = "compravel"
            motivo = "elástico + preço ≤ €9 + cor boa"
        elif preco <= 14 and decisao == "descartado":
            decisao = "medio"
            motivo = "elástico + preço ≤ €14"

    # Override SEM elástico (decisão do dono + feedback de votação):
    #   só vale se a cor for preto / branco / azul marinho.
    #   preto → até €15 · branco/navy → até €10.
    #   fora dessas cores → descarta. EXCEÇÃO: etiqueta visível → não descarta (revisar).
    if not tem_elastico and preco:
        cor_nome = (cor.get("cor_principal") or "").lower()
        is_preto = "preto" in cor_nome or "negro" in cor_nome
        is_branco_navy = ("branco" in cor_nome or "blanco" in cor_nome
                          or "marinho" in cor_nome or "navy" in cor_nome)
        cor_elite = is_preto or is_branco_navy
        cap = 15 if is_preto else (10 if is_branco_navy else 0)

        # (cor não-elite sem etiqueta já foi excluída no bloco de exclusões acima)
        if cor_elite and preco <= cap:
            decisao = "compravel"
            motivo = f"sem elástico, {cor.get('cor_principal')} ≤ €{cap}"
        elif cor_elite:  # cor elite mas acima do cap (preto>15 / branco-navy>10)
            decisao = "descartado"
            motivo = f"sem elástico, {cor.get('cor_principal')} acima de €{cap}"
        elif tem_etiqueta:
            # cor fraca MAS etiqueta visível → não descarta, vale dar uma olhada
            if decisao == "descartado":
                decisao = "medio"
            motivo = "sem elástico, mas etiqueta visível — revisar"

    # Sugestão de negociação (preço a oferecer) — só pra candidatos.
    negociacao = {}
    if decisao in ("compravel", "medio"):
        negociacao = _negociacao(_parse_preco(item.get("preco")), teto, ratio)

    return {
        "score": score,
        "teto": round(teto, 2),
        "preco_num": round(preco, 2) if preco else None,
        "decisao": decisao,
        "motivo": motivo,
        "negociacao": negociacao,
        "breakdown": {
            "tier": pts_tier,
            "tamanho": pts_tam,
            "elastico": pts_el,
            "etiqueta": pts_et,
            "listra_bonus": pts_listra,
            "preco": pts_preco,
            "ratio_preco_teto": round(ratio, 2) if ratio else None,
        },
    }
