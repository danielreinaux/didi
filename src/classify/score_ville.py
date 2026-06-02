"""Score 0-100 + decisão de compra para a Vilebrequin (P0).

A decisão é DIRIGIDA POR FAIXA DE PREÇO (regras explícitas do cliente);
o score 0-100 é uma nota de ranqueamento secundária.

Faixas do cliente (WhatsApp + manual):
  TARTARUGA GRANDE (foco):
    < €40            → comprável sempre (dentro de S-XL)
    €40-60           → comprável "sem muita análise"
    €60-80           → comprável se cor preferida, senão médio
    €80-100          → comprável só se cor preferida OU etiqueta, senão médio
  TARTARUGA PEQUENA / LISO (mesma faixa, €25 ótimo, até €40/42):
    liso só vale com cor da whitelist (preto/branco/navy/cinza/musgo/vermelho)
    ≤ €25            → comprável
    €25-42           → comprável se cor preferida, senão médio
    > €42            → descartado
  OUTRO (peixe/coral/âncora/etc.) → descartado (cliente não compra).

Autenticidade (critério central da marca):
  falso                         → descartado
  suspeito                      → teto em médio
  indefinido / sem_foto_bolso   → mantém decisão + flag "verificar"
Desbotado → descartado. Tamanho fora de S/M/L/XL → descartado.

Resultado: >=70 comprável · 45-69 médio · <45 descartado (com overrides de faixa).
"""
import re

from .cor_ville import bucket_cor, e_cor_bonita, cor_aceita_em_liso

# Tetos de preço (€) por padrão — base do cálculo de eficiência de preço.
TETO = {
    "tartaruga_grande": 80,
    "tartaruga_pequena": 42,
    "liso": 42,
}

# Pontos de atributo (compõem 0~70).
PTS_PADRAO = {
    "tartaruga_grande": 40,
    "tartaruga_pequena": 18,
    "liso": 25,
    "indefinido": 0,
}
PTS_COR = {"preferida": 15, "neutra": 12, "aceitavel": 6, "penalizada": -12}
PTS_TAMANHO = {"M": 15, "L": 12, "S": 8, "XL": 8}
PTS_ETIQUETA = 5
PTS_AUTH_ORIGINAL = 5

# Tipos que já vieram excluídos das etapas anteriores (regex/marca).
EXCLUI_UPSTREAM = {
    "nao_ville": "nao_ville",
    "nao_vilebrequin": "nao_vilebrequin",
    "nao_short": "nao_short",
    "falso": "autenticidade_falsa",
    "outro": "padrao_outro_nao_compra",
}


def _parse_preco(preco_str: str | None) -> float | None:
    """'64,00 €' → 64.0"""
    if not preco_str:
        return None
    nums = re.findall(r"[\d,\.]+", preco_str)
    if not nums:
        return None
    try:
        return float(nums[0].replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _preco_efetivo(item: dict) -> float | None:
    """Preço que o comprador paga = item + proteção (campo preco_total),
    com trava de sanidade (proteção ~5%+€0.70; fora disso usa o base)."""
    base = _parse_preco(item.get("preco"))
    total = _parse_preco(item.get("preco_total"))
    if total is not None and base is not None:
        if base <= total <= base * 1.4 + 2:
            return total
        return base
    return total if base is None else base


def _tamanho_key(tamanho: str | None, titulo: str | None = None) -> str | None:
    """Retorna 'S'|'M'|'L'|'XL' se aceito, ou None se inválido (XS/XXL/numérico/etc.)."""
    t = (tamanho or "").strip().upper()
    if not t:
        return "L"  # sem info → assume L (não penaliza, não exclui)
    # Inválidos explícitos primeiro.
    if re.search(r"\bXX+L\b|\bXXL\b|\bXS\b", t):
        return None
    if ("talla" in t.lower() or "única" in t.lower() or "unica" in t.lower()):
        return None
    for key in ("XL", "M", "L", "S"):  # XL antes de L
        if re.search(rf"\b{key}\b", t):
            return key
    # Numérico (a Ville é coletada por size_id S/M/L/XL; numérico = suspeito)
    if re.search(r"\b\d{2}\b", t):
        return None
    return "L"


def _cor_principal(item: dict) -> str | None:
    """Cor: prioriza o classificador dedicado (cor), cai pro da tartaruga."""
    cor = item.get("cor") if isinstance(item.get("cor"), dict) else {}
    tart = item.get("tartaruga") if isinstance(item.get("tartaruga"), dict) else {}
    return cor.get("cor_principal") or tart.get("cor_principal")


def _tem_etiqueta(item: dict) -> bool:
    """Hang-tag de papel na foto OU anúncio 'novo com etiqueta' (igual ao Sundek)."""
    etiqueta = item.get("etiqueta") or {}
    if etiqueta.get("tem_etiqueta") is True:
        return True
    estado = (item.get("estado") or "").lower()
    declarado = ("etiqueta" in estado or "etichett" in estado or "tag" in estado) and not (
        "sin " in estado or "sem " in estado or "without" in estado or "senza" in estado
    )
    return declarado


def calcular_score(item: dict) -> dict:
    """Retorna dict com score, teto, decisao, motivo, flags e breakdown."""
    cl = item.get("classificacao") or {}
    tipo = cl.get("tipo")

    # Falha de classificação (cota/rede) ou item nunca classificado (tipo vazio)
    # — não foi julgado, reprocessar. Não entra como candidato na votação.
    if tipo == "erro" or not tipo:
        return {"score": 0, "teto": 0, "decisao": "nao_classificado",
                "motivo": "sem classificação (erro/cota/rede) — reprocessar", "breakdown": {}}

    # Autenticidade: prioriza o módulo dedicado (item.autenticidade), cai pro marca_check.
    auth_block = item.get("autenticidade") if isinstance(item.get("autenticidade"), dict) else {}
    marca = item.get("marca_check") or {}
    autenticidade = auth_block.get("autenticidade") or marca.get("autenticidade") or "indefinido"

    cor_nome = _cor_principal(item)
    cor_bucket = bucket_cor(cor_nome)
    tam_key = _tamanho_key(item.get("tamanho"), item.get("titulo"))
    preco = _preco_efetivo(item)
    tem_etiqueta = _tem_etiqueta(item)
    aparencia = (item.get("tartaruga") or {}).get("aparencia") if isinstance(item.get("tartaruga"), dict) else None

    # ── Exclusões diretas (score 0 / descartado) ─────────────────────────
    exclusoes = []
    if tipo in EXCLUI_UPSTREAM:
        exclusoes.append(EXCLUI_UPSTREAM[tipo])
    if autenticidade == "falso":
        exclusoes.append("autenticidade_falsa")
    if aparencia == "desbotado":
        exclusoes.append("desbotado")
    if tam_key is None:
        exclusoes.append("tamanho_invalido")
    if tipo == "liso" and not cor_aceita_em_liso(cor_nome):
        exclusoes.append("cor_liso_fora_whitelist")

    if exclusoes:
        return {"score": 0, "teto": 0, "decisao": "descartado",
                "motivo_exclusao": ", ".join(dict.fromkeys(exclusoes)), "breakdown": {}}

    # ── Score de atributos (0~70) ────────────────────────────────────────
    pts_padrao = PTS_PADRAO.get(tipo, 0)
    pts_cor = PTS_COR.get(cor_bucket, 0)
    pts_tam = PTS_TAMANHO.get(tam_key or "L", 12)
    pts_et = PTS_ETIQUETA if tem_etiqueta else 0
    pts_auth = PTS_AUTH_ORIGINAL if autenticidade == "original" else 0
    pts_atributos = max(0, pts_padrao + pts_cor + pts_tam + pts_et + pts_auth)

    # ── Eficiência de preço (0~30) ───────────────────────────────────────
    teto = TETO.get(tipo, 42)
    pts_preco = 0
    ratio = None
    if preco and teto > 0:
        ratio = preco / teto
        if ratio <= 0.50:
            pts_preco = 30
        elif ratio <= 0.70:
            pts_preco = 20
        elif ratio <= 0.85:
            pts_preco = 10
        elif ratio <= 1.00:
            pts_preco = 5

    score = min(100, pts_atributos + pts_preco)

    # ── Decisão por faixa de preço (autoritativa) ────────────────────────
    cor_bonita = e_cor_bonita(cor_nome)
    flags: list[str] = []
    decisao, motivo = "medio", ""

    if preco is None:
        decisao, motivo = "medio", "sem preço — verificar manualmente"
    elif tipo == "tartaruga_grande":
        if preco <= 60:
            decisao = "compravel"  # < €40 e €40-60 → compra "sem muita análise"
        elif preco <= 80:
            decisao = "compravel" if cor_bonita else "medio"
            motivo = "" if cor_bonita else "€60-80: depende da cor"
        elif preco <= 100:
            if cor_bonita or tem_etiqueta:
                decisao = "compravel"
            else:
                decisao, motivo = "medio", "€80-100: só com cor preferida ou etiqueta"
        else:
            decisao, motivo = "descartado", f"preço €{preco:.2f} acima da faixa (€100)"
    elif tipo in ("tartaruga_pequena", "liso"):
        cor_boa = cor_bucket in ("preferida", "neutra")
        if preco <= 25:
            decisao = "compravel" if (tipo == "liso" or cor_boa) else "medio"
            motivo = "" if (tipo == "liso" or cor_boa) else "tartaruga pequena: cor não-neutra"
        elif preco <= 42:
            decisao = "compravel" if cor_bonita else "medio"
            motivo = "" if cor_bonita else "€25-42: só com cor preferida"
        else:
            decisao, motivo = "descartado", f"preço €{preco:.2f} acima da faixa (€42)"
    elif tipo == "indefinido":
        decisao, motivo = "medio", "padrão indefinido — rever fotos"
        flags.append("rever_fotos")
    else:
        decisao, motivo = "descartado", f"tipo não-comprável ({tipo})"

    # ── Modificadores de autenticidade ───────────────────────────────────
    if autenticidade == "suspeito" and decisao == "compravel":
        decisao = "medio"
        motivo = "autenticidade suspeita — analisar antes de comprar"
    if autenticidade in ("indefinido", "sem_foto_bolso") and decisao in ("compravel", "medio"):
        flags.append("verificar_autenticidade")

    if decisao == "descartado" and not motivo:
        motivo = "fora das faixas de compra"

    return {
        "score": score,
        "teto": teto,
        "preco_num": round(preco, 2) if preco else None,
        "decisao": decisao,
        "motivo": motivo,
        "flags": flags,
        "breakdown": {
            "padrao": pts_padrao,
            "cor": pts_cor,
            "tamanho": pts_tam,
            "etiqueta": pts_et,
            "autenticidade": pts_auth,
            "preco": pts_preco,
            "ratio_preco_teto": round(ratio, 2) if ratio else None,
            "cor_bucket": cor_bucket,
        },
    }
