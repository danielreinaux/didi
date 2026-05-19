"""Score 0-100 por item. Combina qualidade dos atributos + eficiência de preço.

Score = atributos (0~70) + eficiência de preço (0~30)
Resultado:
  >= 70 → comprável
  45~69 → médio (tenta barganha)
  < 45  → descartado
"""
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
PTS_ELASTICO = 15    # com elástico
PTS_SEM_ELASTICO = -15  # sem elástico — perde muita pontuação (doc 1.2)
PTS_ETIQUETA = 10    # com etiqueta
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


def _tamanho_key(tamanho: str | None) -> str:
    if not tamanho:
        return "L"
    t = (tamanho or "").strip().upper()
    for key in ("XL", "XXL", "M", "L", "S"):
        if key in t:
            return key
    # Numeric (31, 32, 33, 34 → L equivalent)
    if re.search(r"\b(29|30|31|32|33|34)\b", t):
        return "L"
    return "L"


def _tamanho_numerico(tamanho: str | None) -> int | None:
    """Retorna o tamanho numérico se for boardshort (ex: '32', '34'), senão None."""
    if not tamanho:
        return None
    m = re.search(r"\b(2[5-9]|3[0-9])\b", (tamanho or ""))
    return int(m.group()) if m else None


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
    tier_final = cor.get("tier_final") or cor.get("tier") or "ruim"
    tamanho = item.get("tamanho") or ""
    tam_key = _tamanho_key(tamanho)
    tem_elastico = elastico.get("tem_elastico") is True
    tipo_fechamento = elastico.get("tipo_fechamento") or ("elastico" if tem_elastico else "sem")
    tem_etiqueta = etiqueta.get("tem_etiqueta") is True
    listra_salva = cor.get("listra_tier") == "salva"
    bicolor = cl.get("bicolor", False)
    tecido_brilhoso = cl.get("tecido_brilhoso", False)
    tem_bolso_frontal = cl.get("tem_bolso_frontal", False)
    listra_na_frente = cl.get("listra_na_frente", False)

    # Filtros de exclusão → score 0
    exclusoes = []
    if tipo in ("estampado", "logo_grande", "nao_sundek", "nao_short"):
        exclusoes.append(tipo)
    if cl.get("aparencia") == "desbotado" or tipo == "desbotado":
        exclusoes.append("desbotado")
    if tier_final == "ruim":
        exclusoes.append("cor_ruim")
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
    # Tamanho numérico fora de 31-34 sem elástico = exclusão (doc 1.2)
    num = _tamanho_numerico(tamanho)
    if num is not None and not tem_elastico and not (31 <= num <= 34):
        exclusoes.append(f"tamanho_numerico_{num}_sem_elastico")

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
    preco = _parse_preco(item.get("preco_total")) or _parse_preco(item.get("preco"))

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

    # Até €10: ok passa, ruim já foi excluído acima
    if preco and preco <= 10 and tier_final != "ruim" and decisao == "descartado":
        decisao = "compravel"
        motivo = "preço ≤ €10"

    return {
        "score": score,
        "teto": round(teto, 2),
        "preco_num": round(preco, 2) if preco else None,
        "decisao": decisao,
        "motivo": motivo,
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
