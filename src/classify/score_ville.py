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
    liso só vale com cor da whitelist (preto/branco/navy/cinza/musgo — vermelho NÃO)
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
import math
import re

from .cor_ville import bucket_cor, bucket_cor_item, e_cor_bonita, e_fundo_problematico, cor_aceita_em_liso

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
# XL nerfado de 8→3 a pedido do dono (17/06): "estou pensando em nerfar um pouco
# o XL". É PROVISÓRIO — confirmar o valor final com o Marcos (ele não fechou número).
PTS_TAMANHO = {"M": 15, "L": 12, "S": 8, "XL": 3}
PTS_ETIQUETA = 5
PTS_AUTH_ORIGINAL = 5
# Coleção antiga (cordão cinza) — penaliza, NÃO exclui.
PTS_COLECAO_ANTIGA = -8

# Tipos que já vieram excluídos das etapas anteriores (regex/marca).
EXCLUI_UPSTREAM = {
    "nao_ville": "nao_ville",
    "nao_vilebrequin": "nao_ville",  # alias legado (P3): unificado em nao_ville
    "nao_short": "nao_short",
    "infantil": "infantil",
    "falso": "autenticidade_falsa",
    "outro": "padrao_outro_nao_compra",
    "sem_evidencia": "sem_evidencia_produto",  # foto não mostra o produto
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


def _oferta_redonda(base: float) -> int:
    """Oferta 'psicológica': maior múltiplo de 5 abaixo do preço-base, com piso de
    80% do base (não ofender em item barato). Ex: 64 → 60 · 58 → 55 · 35 → 30."""
    alvo5 = math.floor((base - 0.01) / 5) * 5
    piso = round(base * 0.80)
    return max(int(alvo5), int(piso), 1)


def _negociacao_ville(base: float | None, teto: float, ratio: float | None,
                      cor_bonita: bool, decisao: str) -> dict:
    """Como abordar o vendedor (a 'fazer oferta' do Vinted é sobre o preço BASE).

    Três modos:
      - urgente: peça comprável + cor bonita + muito barata (ratio ≤ 0,75) →
        dispara o pedido de desconto MAS já chama pra comprar. É a filosofia do
        dono (áudio 18/06): "manda a oferta, monitora uns ~5 min; se o vendedor
        não responder, compra já pra não perder". A decisão final (esperar x
        comprar) é dele — por isso a flag `comprar_ja`.
      - fechar: preço dentro do teto → oferta redonda um pouco abaixo.
      - negociar: preço acima do teto → pedir 'best price', alvo = teto.
    """
    if not base:
        return {}
    # Caso especial do dono: ótima + barata → "não perca".
    if decisao == "compravel" and cor_bonita and ratio is not None and ratio <= 0.75:
        oferta = _oferta_redonda(base)
        return {
            "modo": "fechar",
            "oferta": oferta,
            "comprar_ja": True,
            "msg": (f"⚡ Ótima e barata — peça desconto (oferta €{oferta} / best price) e "
                    f"monitore ~5 min. Se não responder, COMPRE JÁ pra não perder."),
        }
    # Preço já dentro do teto → fechar com oferta redonda.
    if ratio is not None and ratio <= 1.0:
        oferta = _oferta_redonda(base)
        return {
            "modo": "fechar",
            "oferta": oferta,
            "msg": f"💰 Oferecer €{oferta} — \"por {oferta} aceita?\". Se recusar, ainda vale o preço pedido.",
        }
    # Preço acima do teto → negociar pra baixo, alvo = teto da faixa.
    alvo = int(round(teto)) if teto else None
    return {
        "modo": "negociar",
        "oferta": alvo,
        "msg": (f"🗨️ Pedir desconto: \"What's your best price?\" — alvo ≤ €{alvo}."
                if alvo else "🗨️ Pedir: \"What's your best price?\""),
    }


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


def e_colecao_antiga(item: dict) -> bool:
    """Coleção antiga = cordão CINZA (regra do dono).

    Branco / colorido / sem_cordao / indefinido → NÃO conta como antiga
    (na dúvida, não penaliza — mesma postura do Sundek pra dúvida).
    """
    cordao = item.get("cordao") if isinstance(item.get("cordao"), dict) else {}
    return cordao.get("cordao_cor") == "cinza"


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
    # bucket_cor_item: penaliza fundo multicolor/gradiente como se fosse neon.
    cor_bucket = bucket_cor_item(item)
    fundo_problema = e_fundo_problematico(item)
    tam_key = _tamanho_key(item.get("tamanho"), item.get("titulo"))
    preco = _preco_efetivo(item)
    tem_etiqueta = _tem_etiqueta(item)
    aparencia = (item.get("tartaruga") or {}).get("aparencia") if isinstance(item.get("tartaruga"), dict) else None
    fundo_padrao = (item.get("tartaruga") or {}).get("fundo_padrao") if isinstance(item.get("tartaruga"), dict) else None
    fecho = item.get("fecho") if isinstance(item.get("fecho"), dict) else {}
    tipo_fecho = fecho.get("tipo_fechamento")

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
    # Degradê: descarte direto (dono 17/06 — "o padrão degradê pode cortar, não
    # precisa nem nerfar"). O fundo MULTICOLOR (manchas/blocos, sem transição)
    # continua só nerfando (teto em médio) até o Marcos confirmar se também corta.
    if fundo_padrao == "gradiente":
        exclusoes.append("fundo_gradiente")
    # Fecho: o cliente só compra cordão (e elástico). Fivela/botão/velcro →
    # descarte, independente de preço e cor (dono 17/06). Conservador: só exclui
    # quando o detector tem CERTEZA — "indefinido" NÃO exclui (prioriza recall).
    if tipo_fecho in ("botao", "fivela", "velcro"):
        exclusoes.append(f"fecho_{tipo_fecho}")

    if exclusoes:
        return {"score": 0, "teto": 0, "decisao": "descartado",
                "motivo_exclusao": ", ".join(dict.fromkeys(exclusoes)), "breakdown": {}}

    # ── Score de atributos (0~70) ────────────────────────────────────────
    pts_padrao = PTS_PADRAO.get(tipo, 0)
    pts_cor = PTS_COR.get(cor_bucket, 0)
    # Nerf extra de ranking pra fundo multicolor/gradiente (-12 do bucket + -8 = -20 total).
    # Mantém honesto o ordenamento entre itens "uniforme penalizada" (neon) vs multicolor.
    pts_fundo = -8 if fundo_problema else 0
    pts_tam = PTS_TAMANHO.get(tam_key or "L", 12)
    pts_et = PTS_ETIQUETA if tem_etiqueta else 0
    pts_auth = PTS_AUTH_ORIGINAL if autenticidade == "original" else 0
    # Coleção antiga (cordão cinza) penaliza em todos os tipos. Não exclui.
    colecao_antiga = e_colecao_antiga(item)
    pts_colecao = PTS_COLECAO_ANTIGA if colecao_antiga else 0
    pts_atributos = max(0, pts_padrao + pts_cor + pts_fundo + pts_tam + pts_et + pts_auth + pts_colecao)

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
    # Fundo multicolor cancela "cor bonita" — visual confuso não vale como preferida
    # mesmo se a cor dominante for navy/vermelho/etc.
    cor_bonita = e_cor_bonita(cor_nome) and not fundo_problema
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
    # Estampado sem foto do bolso: não dá pra confirmar original (e o estampado
    # SEMPRE tem bolso — dono 17/06). Em vez de subir como comprável, o caminho
    # mais barato é PEDIR a foto traseira ao vendedor → rebaixa pra médio com
    # ação clara. (Estampado que comprovadamente NÃO tem bolso já vira "falso"
    # na etapa de autenticidade e cai nas exclusões acima.)
    estampado = tipo in ("tartaruga_grande", "tartaruga_pequena")
    if estampado and autenticidade == "sem_foto_bolso":
        flags.append("pedir_foto_traseira")
        if decisao == "compravel":
            decisao = "medio"
            motivo = "estampado sem foto do bolso — pedir foto traseira ao vendedor"
    if autenticidade in ("indefinido", "sem_foto_bolso") and decisao in ("compravel", "medio"):
        flags.append("verificar_autenticidade")
    # Coleção antiga (cordão cinza) já penaliza o score; expõe também como flag
    # pra aparecer na votação e o dono decidir caso a caso pelo preço (17/06).
    if colecao_antiga:
        flags.append("colecao_antiga")

    # ── Teto em medio pra fundo multicolor (Opção B) ─────────────────────
    # Multicolor/gradiente nunca vira compravel automático — força revisão humana.
    if fundo_problema:
        flags.append("fundo_multicolor")
        if decisao == "compravel":
            decisao = "medio"
            motivo = "fundo multicolor/gradiente — revisar antes de comprar"

    if decisao == "descartado" and not motivo:
        motivo = "fora das faixas de compra"

    # ── Sugestão de negociação (preço a oferecer) — só pra candidatos ─────
    # Usa o preço-base (não o efetivo): a oferta do Vinted é sobre o pedido.
    negociacao = {}
    if decisao in ("compravel", "medio"):
        negociacao = _negociacao_ville(
            _parse_preco(item.get("preco")), teto, ratio, cor_bonita, decisao
        )

    return {
        "score": score,
        "teto": teto,
        "preco_num": round(preco, 2) if preco else None,
        "decisao": decisao,
        "motivo": motivo,
        "flags": flags,
        "negociacao": negociacao,
        "breakdown": {
            "padrao": pts_padrao,
            "cor": pts_cor,
            # fundo só aparece quando há nerf, pra não poluir a linha "por_que".
            **({"fundo": pts_fundo} if pts_fundo else {}),
            "tamanho": pts_tam,
            "etiqueta": pts_et,
            "autenticidade": pts_auth,
            # colecao só aparece quando há penalidade (cordão cinza), mesmo padrão do fundo.
            **({"colecao_antiga": pts_colecao} if pts_colecao else {}),
            "preco": pts_preco,
            "ratio_preco_teto": round(ratio, 2) if ratio else None,
            "cor_bucket": cor_bucket,
            "fundo_problema": fundo_problema,
            "colecao_antiga": colecao_antiga,
        },
    }
