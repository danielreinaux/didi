"""Vinted UK (vinted.co.uk): coleta dos anúncios novos e conversão de libra para euro (18/11/2026).

O UK entra na mesma rodada da Espanha, depois dela, num contexto próprio do navegador:
  - olha os UK_MAX_LISTA anúncios mais novos do catálogo e abre só os que ainda não estão no
    acervo, até UK_MAX_NOVOS por rodada. Anúncio já visto não é reaberto aqui; vendido, preço e
    fotos dele são acompanhados pelo verifica_vendidos, como os da Espanha que saem do topo;
  - qualquer falha devolve o que já tiver coletado: o UK nunca derruba a coleta da Espanha.

Preço: o vinted.co.uk mostra "£7.00" e o total com a proteção ao comprador ("£8.05" = 5% + £0,70).
O score, o app e o e-mail trabalham em euro, então `preco`, `preco_total` e `envio` são gravados
convertidos por config.GBP_EUR, no formato do vinted.es ("8,40 €"); os textos originais ficam em
`preco_gbp`, `preco_total_gbp` e `envio_gbp`, e o anúncio ganha `site: "uk"`.
"""
import json
import re
import time
from pathlib import Path

from ..config import GBP_EUR, UK_MAX_LISTA, UK_MAX_NOVOS, VINTED

SITE = "uk"
BASE_URL = VINTED["uk_base_url"]
MOEDA = "GBP"

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")


def libras(txt) -> float | None:
    """"£7.00" / "from £2.49" / "£1,250.00" → 7.0 / 2.49 / 1250.0."""
    m = re.search(r"(\d[\d,]*(?:\.\d{1,2})?)", str(txt or "").replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def texto_euro(valor: float) -> str:
    """8.4 → "8,40 €" (mesmo formato do vinted.es, que o resto do código já lê)."""
    return f"{valor:.2f}".replace(".", ",") + "\xa0€"


def converter(item: dict) -> dict:
    """Anúncio extraído do vinted.co.uk → preços em euro, libra guardada ao lado."""
    item["site"] = SITE
    item["moeda_original"] = MOEDA
    item["cambio"] = GBP_EUR
    for campo in ("preco", "preco_total"):
        v = libras(item.get(campo))
        if v is not None:
            item[f"{campo}_gbp"] = item.get(campo)
            item[campo] = texto_euro(v * GBP_EUR)
    envio = item.get("envio")
    v = libras(envio)
    if v is not None:
        item["envio_gbp"] = envio
        desde = "desde " if str(envio).strip().lower().startswith("from") else ""
        item["envio"] = desde + texto_euro(v * GBP_EUR)
    return item


def atualizar_preco(item: dict, preco_gbp: float) -> str:
    """O verifica_vendidos leu `preco_gbp` na página de um anúncio do UK: regrava libra e euro se
    mudou. Devolve o resumo da mudança ("" se não mudou)."""
    velho = libras(item.get("preco_gbp"))
    if velho is None or abs(preco_gbp - velho) < 0.01:
        return ""
    total = preco_gbp * 1.05 + 0.70  # proteção ao comprador do UK: 5% + £0,70
    item.setdefault("preco_inicial", item.get("preco"))
    item["preco_gbp"] = f"£{preco_gbp:.2f}"
    item["preco_total_gbp"] = f"£{total:.2f}"
    item["preco"] = texto_euro(preco_gbp * GBP_EUR)
    item["preco_total"] = texto_euro(total * GBP_EUR)
    return f"preço £{velho:g}→£{preco_gbp:g}"


def ids_conhecidos(acervo: Path) -> set[str]:
    """Ids do acervo da marca (tudo que já foi coletado, de qualquer site)."""
    try:
        return {str(x.get("id")) for x in json.loads(acervo.read_text(encoding="utf-8")) if x.get("id")}
    except Exception:  # noqa: BLE001 — sem acervo, tudo é novo (o teto UK_MAX_NOVOS segura)
        return set()


def coletar(browser, url_catalogo: str, acervo: Path, ja_coletados: set[str] | None = None,
            marca_nav: str | None = None) -> list[dict]:
    """Anúncios novos do catálogo do UK, já convertidos para euro. Nunca lança exceção.
    `marca_nav`: marca do navegador para o teto por anúncio (scrape/vigia.py)."""
    from ..config import TETO_ANUNCIO_S
    from ..scrape import vigia
    from ..scrape.extract import extract_item
    from .vinted import listar_urls_items

    t0 = time.time()
    coletados: list[dict] = []
    contexto = None
    try:
        conhecidos = ids_conhecidos(acervo) | set(ja_coletados or ())
        contexto = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-GB", user_agent=_UA)
        page = contexto.new_page()
        print(f"\n[UK] Catálogo do vinted.co.uk:\n    {url_catalogo}")
        page.goto(url_catalogo, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        urls = listar_urls_items(page, UK_MAX_LISTA)
        novos = [u for u in urls if (m := re.search(r"/items/(\d+)", u)) and m.group(1) not in conhecidos]
        print(f"    {len(urls)} anúncios no topo, {len(novos)} ainda não vistos"
              + (f" (abrindo {UK_MAX_NOVOS} nesta rodada)" if len(novos) > UK_MAX_NOVOS else ""))
        for i, u in enumerate(novos[:UK_MAX_NOVOS]):
            print(f"    [UK {i + 1}/{min(len(novos), UK_MAX_NOVOS)}] {u}")
            with vigia.Teto(TETO_ANUNCIO_S, marca_nav) as teto:
                try:
                    item = converter(extract_item(page, u))
                    print(f"        {item['titulo']} — {item.get('preco_gbp')} (≈ {item['preco']}) · "
                          f"{item['tamanho']} · {item['estado']} · {len(item.get('fotos') or [])} fotos")
                    coletados.append(item)
                except Exception as e:  # noqa: BLE001
                    print(f"        ERRO: {str(e)[:120]}")
            if teto.estourou:
                # O navegador foi fechado à força: o resto do UK fica para a rodada seguinte
                # (anúncio não coletado continua "ainda não visto").
                print(f"        TRAVOU: passou de {TETO_ANUNCIO_S} s neste anúncio; o resto do UK fica para a próxima rodada")
                break
    except Exception as e:  # noqa: BLE001 — o UK nunca derruba a coleta da Espanha
        print(f"    [UK] falhou: {str(e)[:200]}")
    finally:
        if contexto is not None:
            try:
                contexto.close()
            except Exception:
                pass
    sem_foto = sum(1 for x in coletados if not x.get("fotos"))
    if coletados and sem_foto * 2 > len(coletados):
        print(f"::warning::[UK] {sem_foto} de {len(coletados)} anúncios do UK vieram sem foto — "
              "conferir o extract_item no vinted.co.uk")
    print(f"    [UK] {len(coletados)} anúncio(s) novo(s) em {time.time() - t0:.0f}s")
    return coletados
