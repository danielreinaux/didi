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
PTS_ETIQUETA = 10    # hang-tag de papel visível na foto
PTS_LISTRA_SALVA = 5 # bônus quando listra salva a cor

# Condição DECLARADA no anúncio (manual 1.7: Novo c/etiq > Novo s/etiq > Muito bom).
# Sinal independente do hang-tag visual (PTS_ETIQUETA) — os dois podem somar.
PTS_CONDICAO = {
    "nuevo_con_etiquetas": 8,
    "nuevo_sin_etiquetas": 5,
    "muy_bueno":           2,
    "bueno":               0,   # abaixo do manual, sem bônus
}

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


def _condicao_key(estado: str | None) -> str | None:
    """Normaliza o 'estado' da listagem (espanhol/pt/en) p/ uma chave de PTS_CONDICAO."""
    if not estado:
        return None
    e = estado.lower().strip()
    if "etiqueta" in e or "etichett" in e or "tag" in e:
        if "sin " in e or "sem " in e or "without" in e or "senza" in e:
            return "nuevo_sin_etiquetas"
        return "nuevo_con_etiquetas"
    if "muy bueno" in e or "muito bom" in e or "very good" in e or "ottimo" in e:
        return "muy_bueno"
    if "bueno" in e or "bom" in e or "good" in e or "buono" in e:
        return "bueno"
    return None


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
    tem_bolso_traseiro = cl.get("tem_bolso_traseiro")  # None = indefinido (não exclui)

    # Filtros de exclusão → score 0
    exclusoes = []
    if tipo in ("estampado", "logo_grande", "nao_sundek", "nao_short", "tamanho_invalido", "infantil"):
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
    if tem_bolso_traseiro is False:
        exclusoes.append("sem_bolso_traseiro")
    # Bolso traseiro só com logo (sem nome SUNDEK) = coleção antiga, exclui
    if tem_bolso_traseiro is True and cl.get("bolso_traseiro_tem_nome") is False:
        exclusoes.append("bolso_so_logo_colecao_antiga")
    if tipo == "liso" and cl.get("tem_listra_lateral_sundek") is False:
        exclusoes.append("sem_listra_sundek")
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
    pts_cond = PTS_CONDICAO.get(_condicao_key(item.get("estado")), 0)
    pts_atributos = max(0, pts_tier + pts_tam + pts_el + pts_et + pts_listra + pts_cond)

    # Parte 2 — Eficiência de preço (0~30)
    teto = calcular_teto(tier_final, tamanho, tem_elastico, tem_etiqueta)
    # preco_total do Vinted é instável (captura envio ou outros valores) — usar só preco
    preco = _parse_preco(item.get("preco"))

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

    # Override SEM elástico (manual 1.2 + decisão do dono):
    # teto duro €25; mas pechincha com cor elite compra mesmo sem elástico.
    if not tem_elastico and preco:
        if preco > 25:
            decisao = "descartado"
            motivo = f"sem elástico + preço €{preco:.2f} > €25 (teto do manual)"
        elif tier_final == "maravilhoso" and preco <= 10:
            decisao = "compravel"
            motivo = "sem elástico mas cor perfeita + preço ≤ €10 (pechincha)"
        elif tier_final in ("boa", "muito_boa", "maravilhoso") and decisao == "descartado":
            decisao = "medio"
            motivo = "sem elástico + cor boa+ + preço ≤ €25 (barganha)"

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
            "condicao": pts_cond,
            "listra_bonus": pts_listra,
            "preco": pts_preco,
            "ratio_preco_teto": round(ratio, 2) if ratio else None,
        },
    }
