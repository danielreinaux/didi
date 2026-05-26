"""Pré-filtro por título — descarta peças que claramente NÃO são shorts antes
de gastar chamada de IA. Regex-only, custo zero.
"""
import re
from typing import NamedTuple

from ..config import SUNDEK


class Resultado(NamedTuple):
    ok: bool
    motivo: str | None
    # categoria: "nao_short" (peça não é short) ou "tamanho_invalido" (é short mas tamanho errado)
    # None quando ok=True.
    categoria: str | None = None


# (regex, motivo)
EXCLUSAO: list[tuple[re.Pattern, str]] = [
    # tops
    (re.compile(r"\bt[-\s]?shirts?\b", re.I), "t-shirt"),
    (re.compile(r"\bmaglietta?s?\b", re.I), "maglietta (camiseta italiana)"),
    (re.compile(r"\bcamiseta\b", re.I), "camiseta"),
    (re.compile(r"\bpolo\b", re.I), "polo"),
    (re.compile(r"\bcamicia\b", re.I), "camicia (camisa italiana)"),
    (re.compile(r"\bcamisa\b", re.I), "camisa"),
    (re.compile(r"\bblusa\b", re.I), "blusa"),
    (re.compile(r"\btanktop\b|\btank[-\s]top\b", re.I), "tank top"),
    (re.compile(r"\bhoodie\b|\bsweatshirt\b", re.I), "moletom"),

    # agasalhos
    (re.compile(r"\bfelpa\b", re.I), "felpa (moletom italiano)"),
    (re.compile(r"\bmaglion(e|cino)\b", re.I), "maglione (suéter italiano)"),
    (re.compile(r"\bsweater\b|\bsuet[eé]r\b|\bsu[eé]ter\b", re.I), "suéter"),
    (re.compile(r"\bjersey\b", re.I), "jersey"),
    (re.compile(r"\bgiacca\b|\bjacket\b|\bjaqueta\b|\bblazer\b", re.I), "jaqueta/casaco"),
    (re.compile(r"\bcappotto\b|\bcoat\b|\bcasaco\b", re.I), "casaco"),

    # calças longas — em italiano, "pantalone/i" pode ser calça OU bermuda dependendo do contexto.
    # Só excluímos quando NÃO há indicação de short (corto, corti, short, bagno, mare, costume).
    (re.compile(r"\bpants\b|\bcal[cç]a\b", re.I), "calça longa"),
    (re.compile(r"\bjeans?\b", re.I), "jeans"),
    # pantalone(s) sem qualquer indicador de short = provavelmente calça
    # (usamos lookahead negativo: pantalone(i) NÃO seguido por corto/corti/short/bagno/mare/costume)
    (re.compile(r"\bpantalon[ei]\b(?!.*(?:cort[oi]|short|bagno|mare|costume|cargo))", re.I), "calça longa"),

    # íntimos / sungas
    (re.compile(r"\bslip\b", re.I), "slip (sunga)"),
    (re.compile(r"\bsunga\b", re.I), "sunga"),
    (re.compile(r"\b[ií]ntimo\b|\bunderwear\b|\bbox(er)?\s+brief\b", re.I), "roupa íntima"),

    # acessórios
    (re.compile(r"\binfradito\b|\bflip[-\s]?flop\b|\bchinelo\b", re.I), "chinelo"),
    (re.compile(r"\bcappello\b|\bhat\b|\bbon[eé]\b|\bcap\b", re.I), "chapéu/boné"),
    (re.compile(r"\bocchiali\b|\bsunglasses\b|\b[óo]culos\b", re.I), "óculos"),
    (re.compile(r"\bcintur[oóa]n?\b|\bbelt\b|\bcinto\b", re.I), "cinto"),
    (re.compile(r"\bborsa\b|\bbag\b|\bbolsa\b|\bzaino\b", re.I), "bolsa"),
    (re.compile(r"\bscarpe?\b|\bshoes\b|\bsapatos?\b|\bsneakers?\b", re.I), "calçado"),

]

# Regras de infantil — retornadas com categoria 'infantil' (não 'nao_short')
EXCLUSAO_INFANTIL: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bbambin[oa]s?\b|\bbimb[oa]\b", re.I), "infantil (bambino)"),
    (re.compile(r"\bragazz[oa]\b", re.I), "infantil (ragazzo)"),
    (re.compile(r"\bni[ñn][oa]\b", re.I), "infantil (niño)"),
    (re.compile(r"\benfant\b|\bgar[çc]on\b", re.I), "infantil (enfant)"),
    (re.compile(r"\bkids?\b|\bchild\b|\bboy\b", re.I), "infantil (kids)"),
    # tamanhos por idade: "taille 10 ans", "tg 14 anni", "10 años", "8 yo"
    (re.compile(r"\b(taille|tg|talla|size)?\s*\d{1,2}\s*(ans|anni|a[ñn]os?|years?|yo)\b", re.I), "infantil (tamanho por idade)"),
]


_TAMANHOS = SUNDEK["tamanhos_aceitos"]


def _tamanho_ok(tamanho: str | None) -> bool:
    if not tamanho:
        return True  # sem info de tamanho → deixa passar, IA decide
    t = tamanho.strip()
    # "Talla única" no Vinted-ES geralmente é piece infantil que vendedor não soube classificar
    # (adulto Sundek sempre tem S/M/L/XL/numérico). Marca como suspeita de tamanho_invalido.
    if "talla" in t.lower() and ("única" in t.lower() or "unica" in t.lower()):
        return False
    for ok in _TAMANHOS:
        if ok.lower() in t.lower():
            return True
    # tamanhos que claramente não servem
    bad = re.compile(r"\b(XXL|XXXL|XS|Talla\s*[úu]nica)\b", re.I)
    if bad.search(t):
        return False
    return True  # dúvida → passa


def _tamanho_numerico_ruim(tamanho: str | None, titulo: str | None) -> int | None:
    """Detecta tamanho numérico fora de 31-34 no campo OU no título. Retorna o número."""
    for txt in (tamanho, titulo):
        if not txt:
            continue
        m = re.search(r"\b(2[5-9]|3[0-9])\b", txt)
        if m:
            n = int(m.group())
            if not (31 <= n <= 34):
                return n
    return None


def parece_short(item: dict) -> Resultado:
    titulo = (item.get("titulo") or "").strip()
    if not titulo:
        return Resultado(False, "sem título", "nao_short")
    for regex, motivo in EXCLUSAO_INFANTIL:
        if regex.search(titulo):
            return Resultado(False, motivo, "infantil")
    for regex, motivo in EXCLUSAO:
        if regex.search(titulo):
            return Resultado(False, motivo, "nao_short")
    # Tamanhos inválidos: a peça PODE ser short, mas o tamanho não serve. Categoria separada.
    if not _tamanho_ok(item.get("tamanho")):
        tam = item.get("tamanho") or "?"
        return Resultado(False, f"tamanho fora do range ({tam})", "tamanho_invalido")
    # Tamanho numérico fora de 31-34 — corta aqui, sem gastar IA. Tipo: tamanho_invalido.
    num = _tamanho_numerico_ruim(item.get("tamanho"), titulo)
    if num is not None:
        return Resultado(False, f"tamanho_numerico_{num}", "tamanho_invalido")
    return Resultado(True, None)
