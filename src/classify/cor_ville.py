"""Regra de cor da Vilebrequin (P0) — pura, sem IA.

A Ville NÃO funciona como o Sundek: aqui a cor quase nunca exclui.
Regras do cliente (manual + WhatsApp):
  - Cores PREFERIDAS ("muito bonitas"): preto, branco, azul escuro/navy,
    vermelho não-alaranjado. São as que liberam compra nas faixas altas (€60-100).
  - Cores NEUTRAS boas: cinza, musgo (verde militar/oliva escuro fosco).
  - Cores ACEITÁVEIS: qualquer outra (laranja, verde, azul médio, etc.) —
    NÃO excluem quando há tartaruga grande; só não dão bônus.
  - NEON/FLUO/METÁLICO: só BAIXAM a nota, nunca excluem (≠ Sundek).

No LISO, porém, o cliente só compra um conjunto fechado de cores
(preto, branco, navy, cinza, musgo, vermelho não-alaranjado). O resto descarta.

Mapeia a `cor_principal` (texto livre que a IA já devolveu) para um "bucket".
"""
import re


def _norm(nome: str | None) -> str:
    return (nome or "").strip().lower()


# Detecta neon/fluo/metálico no texto da cor (só penaliza, não exclui).
_PENALIZA_RE = re.compile(
    r"neon|fluo|fl[úu]or|fluores|metálic|metalic|brilho|brilhant|holog|"
    r"pratead|dourad|ouro|espelhad|satin|acetinad",
    re.IGNORECASE,
)

# Cores preferidas ("muito bonitas") — liberam as faixas altas.
_PRETO_RE = re.compile(r"\bpreto\b|\bnoir\b|\bblack\b|\bnegro\b", re.I)
_BRANCO_RE = re.compile(r"\bbranco\b|\bblanc\b|\bwhite\b|\bbianco\b", re.I)
_NAVY_RE = re.compile(r"navy|marinho|azul\s*escuro|azul\s*marinho|azul\s*navy|bleu\s*marine", re.I)
# vermelho que NÃO seja alaranjado/coral/salmão
_VERMELHO_RE = re.compile(r"vermelh|\bred\b|\brosso\b|\brouge\b", re.I)
_ALARANJADO_RE = re.compile(r"alaranj|laranj|coral|salm|tomate|orange", re.I)

# Cores neutras boas (aceitas no liso, dão bônus médio).
_CINZA_RE = re.compile(r"cinza|cinz|gris|grey|gray|grigio", re.I)
_MUSGO_RE = re.compile(r"musgo|militar|oliva|olive|k[áa]ki\s*escuro|verde\s*militar", re.I)


def e_alaranjado(nome: str | None) -> bool:
    """Vermelho-alaranjado / laranja / coral / salmão (não conta como vermelho preferido)."""
    return bool(_ALARANJADO_RE.search(_norm(nome)))


def bucket_cor(nome: str | None) -> str:
    """Classifica a cor em: preferida | neutra | aceitavel | penalizada.

    'penalizada' = neon/fluo/metálico (só reduz score, nunca exclui na Ville).
    """
    n = _norm(nome)
    if not n:
        return "aceitavel"

    if _PENALIZA_RE.search(n):
        return "penalizada"

    # Vermelho preferido só se NÃO for alaranjado/coral/salmão.
    if _VERMELHO_RE.search(n) and not _ALARANJADO_RE.search(n):
        return "preferida"
    if _PRETO_RE.search(n) or _BRANCO_RE.search(n) or _NAVY_RE.search(n):
        return "preferida"

    if _CINZA_RE.search(n) or _MUSGO_RE.search(n):
        return "neutra"

    return "aceitavel"


def e_cor_bonita(nome: str | None) -> bool:
    """'Cor muito bonita' do cliente = bucket preferida. Libera faixas €60-100."""
    return bucket_cor(nome) == "preferida"


def cor_aceita_em_liso(nome: str | None) -> bool:
    """No liso o cliente só compra: preto, branco, navy, cinza, musgo,
    vermelho não-alaranjado. Qualquer outra cor → descarta."""
    return bucket_cor(nome) in ("preferida", "neutra")
