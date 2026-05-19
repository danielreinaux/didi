"""Pré-filtro por título — descarta peças que claramente NÃO são shorts antes
de gastar chamada de IA. Regex-only, custo zero.
"""
import re
from typing import NamedTuple

from .config import SUNDEK


class Resultado(NamedTuple):
    ok: bool
    motivo: str | None


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

    # calças longas
    (re.compile(r"\bpantalon[ei]\b|\bpants\b|\bcal[cç]a\b", re.I), "calça longa"),
    (re.compile(r"\bjeans?\b", re.I), "jeans"),

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

    # infantil (escapou do size filter)
    (re.compile(r"\bbambin[oa]s?\b|\bbimb[oa]\b", re.I), "infantil (bambino)"),
]


_TAMANHOS = SUNDEK["tamanhos_aceitos"]


def _tamanho_ok(tamanho: str | None) -> bool:
    if not tamanho:
        return True  # sem info de tamanho → deixa passar, IA decide
    t = tamanho.strip()
    for ok in _TAMANHOS:
        if ok.lower() in t.lower():
            return True
    # tamanhos que claramente não servem
    bad = re.compile(r"\b(XXL|XXXL|XS|Talla\s*[úu]nica)\b", re.I)
    if bad.search(t):
        return False
    return True  # dúvida → passa


def parece_short(item: dict) -> Resultado:
    titulo = (item.get("titulo") or "").strip()
    if not titulo:
        return Resultado(False, "sem título")
    for regex, motivo in EXCLUSAO:
        if regex.search(titulo):
            return Resultado(False, motivo)
    if not _tamanho_ok(item.get("tamanho")):
        tam = item.get("tamanho") or "?"
        return Resultado(False, f"tamanho fora do range ({tam})")
    return Resultado(True, None)
