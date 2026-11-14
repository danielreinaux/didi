"""Lista COMPLETA das fotos de um anúncio do Vinted, tirada dos dados embutidos na página.

Por quê (14/11/2026): a galeria na tela mostra no máximo 5 fotos (as outras ficam atrás do
"+N") e o extract_item lia as fotos pelos <img> da tela. Nenhum anúncio chegava à IA com mais
de 5 fotos: 46% do Sundek e 45% da Ville batiam nesse teto, e numa amostra de 18 anúncios
guardados com 5 fotos, 15 tinham mais no Vinted (até 11). Caso que mostrou o problema:
10772630323 (Ville), 11 fotos, as costas só nas fotos 9 e 11 → "sem foto do bolso".

A página traz, nos scripts do Next.js, o bloco `"item_id":"<id>","photos":[{..."url":...}]`
com todas as fotos na ordem do anúncio. As URLs são idênticas às dos <img> da tela (mesmo
tamanho f800, mesma assinatura), então as fotos que já vinham não mudam: completar() devolve
as da tela primeiro e só ACRESCENTA as que faltavam. Se o bloco sumir ou mudar de formato, fica
tudo como antes (só as fotos da tela).
"""
import json
import re

MAX_GUARDADAS = 12  # fotos guardadas por anúncio (o Vinted aceita até 20)

_CHAVE = re.compile(r"/t/([^/]+)/f\d+/([^/?]+)")
_EH_FOTO = re.compile(r"vinted\.net/.*/f\d+/")


def chave(url: str) -> str:
    """Identifica a foto sem depender da assinatura (?s=...) nem do tamanho (f800)."""
    m = _CHAVE.search(url or "")
    return "/".join(m.groups()) if m else (url or "")


def _lista_json(texto: str, inicio: int) -> list | None:
    """Decodifica a lista JSON que começa em texto[inicio] == '['."""
    prof, em_str, esc = 0, False, False
    for k in range(inicio, min(len(texto), inicio + 400_000)):
        ch = texto[k]
        if em_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                em_str = False
        elif ch == '"':
            em_str = True
        elif ch == "[":
            prof += 1
        elif ch == "]":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(texto[inicio:k + 1])
                except Exception:
                    return None
    return None


def fotos_dos_dados(html: str, item_id: str) -> list[str] | None:
    """URLs de todas as fotos do anúncio `item_id`, na ordem do Vinted; None se não achou."""
    if not html or not item_id:
        return None
    # Dentro dos scripts o JSON vem como string JS (aspas escapadas); tenta as duas formas.
    for marca, escapado in (('\\"item_id\\":\\"%s\\",\\"photos\\":[' % item_id, True),
                            ('"item_id":"%s","photos":[' % item_id, False)):
        i = html.find(marca)
        if i == -1:
            continue
        inicio = i + len(marca) - 1
        if escapado:
            trecho = html[inicio:inicio + 400_000].replace('\\"', '"').replace("\\\\", "\\")
            lista = _lista_json(trecho, 0)
        else:
            lista = _lista_json(html, inicio)
        if not isinstance(lista, list):
            continue
        urls = [f.get("url") for f in lista if isinstance(f, dict)]
        urls = [u for u in urls if isinstance(u, str) and _EH_FOTO.search(u)]
        if urls:
            return list(dict.fromkeys(urls))
    return None


def completar(fotos_tela: list[str], html: str, item_id: str) -> list[str]:
    """Fotos da tela + as que só existem nos dados da página, sem repetir. Só acrescenta quando
    os dados são mesmo deste anúncio: pelo menos uma foto da tela tem de estar na lista (ou a
    tela não trouxe nenhuma). Qualquer problema → devolve as fotos da tela, como era antes."""
    fotos_tela = list(fotos_tela or [])
    try:
        dados = fotos_dos_dados(html, str(item_id or ""))
    except Exception:
        dados = None
    if not dados:
        return fotos_tela
    na_tela = {chave(u) for u in fotos_tela}
    if na_tela and not (na_tela & {chave(u) for u in dados}):
        return fotos_tela
    return fotos_tela + [u for u in dados if chave(u) not in na_tela]
