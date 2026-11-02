"""Robô sempre ligado — MODO SOMBRA (teste de ~1 semana numa VPS).

A cada INTERVALO segundos, 24 h por dia: abre o catálogo Sundek (mais recentes primeiro), pega
os anúncios da 1ª página e, para cada id NUNCA visto, abre o anúncio, registra quando a VPS o
viu pela 1ª vez (e o "hace X" da Vinted) e, com CLASSIFICAR=1, classifica igual à produção —
só os publicados nas últimas CLASSIFICAR_ATE_H horas (anúncio antigo "subido" pelo vendedor fica
registrado sem IA), WORKERS de cada vez.
NÃO grava no repositório e NÃO manda e-mail: é só medição. O GitHub Actions segue normal.

Saída (SOMBRA_DIR, padrão ~/didi-sombra):
  vistos.jsonl  — 1 linha por anúncio novo: id, url, visto_em (UTC, leitura do catálogo), upload,
                  titulo, preco, tamanho, decisao/score/motivo e segundos entre ver e decidir
                  (se classificou; "classificado": false se era antigo)
  ciclos.jsonl  — 1 linha por ciclo: início, duração, nº de links, novos, bloqueio/erro

Uso:  HEADLESS=true python -m src.worker.sombra
Relatório:  python -m src.worker.relatorio_sombra
"""
import json
import os
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from playwright.sync_api import sync_playwright  # noqa: E402

from ..build.votacao_items import _publicado_em  # noqa: E402
from ..scrape.extract import extract_item  # noqa: E402
from ..sources.vinted import _extrair_urls_pagina, montar_url_sundek_hombre  # noqa: E402
from ..utils.browser import abrir_sessao_vinted  # noqa: E402

INTERVALO = int(os.environ.get("INTERVALO", "75"))          # segundos entre ciclos
CLASSIFICAR = os.environ.get("CLASSIFICAR", "1") == "1"
CLASSIFICAR_ATE_H = float(os.environ.get("CLASSIFICAR_ATE_H", "24"))  # só gasta IA com anúncio de até X h
WORKERS = int(os.environ.get("WORKERS", "4"))               # classificações em paralelo
RENOVAR_SESSAO_H = float(os.environ.get("RENOVAR_SESSAO_H", "6"))
DIR = Path(os.environ.get("SOMBRA_DIR", Path.home() / "didi-sombra"))
VISTOS = DIR / "vistos.jsonl"
CICLOS = DIR / "ciclos.jsonl"


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{agora()}] {msg}", flush=True)


def gravar(arq: Path, reg: dict) -> None:
    with arq.open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def carregar_vistos() -> set[str]:
    if not VISTOS.exists():
        return set()
    ids = set()
    for linha in VISTOS.read_text(encoding="utf-8").splitlines():
        try:
            ids.add(str(json.loads(linha)["id"]))
        except Exception:
            continue
    return ids


def id_do_link(url: str) -> str | None:
    try:
        return url.split("/items/")[1].split("-")[0].split("?")[0]
    except Exception:
        return None


def links_do_catalogo(page) -> list[str]:
    page.goto(montar_url_sundek_hombre(), wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(1200)
    return _extrair_urls_pagina(page)  # mesma leitura da produção (sem o armário em destaque)


def classificar(item: dict) -> dict:
    """Mesmo caminho da produção (classify/run.py): etapas de IA + score + conferências."""
    from ..classify import run as R
    from ..classify.cor import _normalizar_tier
    from ..classify.desbotado import precisa_checar_aprovado
    from ..classify.score import calcular_score
    from ..utils.listra_tier import avaliar_combo

    it, _, _ = R._processar(dict(item), "sombra", 1)
    cor = it.get("cor")
    if isinstance(cor, dict) and cor.get("tier"):
        _normalizar_tier(cor)
        combo = avaliar_combo(cor.get("cor_principal", "") or "", cor.get("cores_listras") or [], cor.get("tier"))
        cor.update(listra_tier=combo["listra_tier"], tier_final=combo["tier_final"], combo_motivo=combo["motivo"])
    it["score"] = calcular_score(it)
    if R._precisa_confirmar_listra(it):
        R._confirmar_listra(it, calcular_score)
    if precisa_checar_aprovado(it):
        R._checar_aprovado(it, calcular_score)
    return it


def recente(item: dict) -> bool:
    """Publicado há até CLASSIFICAR_ATE_H horas? Anúncio antigo "subido" pelo vendedor volta ao
    topo do catálogo, mas não é o que a medição procura — fica registrado sem gastar IA."""
    pub = _publicado_em(item)
    if not pub:
        return True  # sem "hace X" legível: classifica por garantia
    return datetime.now(timezone.utc) - datetime.fromisoformat(pub) <= timedelta(hours=CLASSIFICAR_ATE_H)


def classificar_linha(linha: dict, item: dict, t_visto: float) -> dict:
    try:
        c = classificar(item)
        s = c.get("score") or {}
        linha.update(decisao=s.get("decisao"), score=s.get("score"),
                     motivo=s.get("motivo_exclusao") or s.get("motivo"))
    except Exception as e:
        linha["erro_classificar"] = str(e)[:200]
    linha["segundos_ate_decisao"] = round(time.time() - t_visto, 1)
    return linha


def ciclo(page_cat, page_item, vistos: set[str], inicial: bool, pool: ThreadPoolExecutor) -> dict:
    t0 = time.time()
    links = links_do_catalogo(page_cat)
    t_visto, visto_em = time.time(), agora()  # todos os novos do ciclo foram vistos agora
    novos = [u for u in links if (i := id_do_link(u)) and i not in vistos]
    reg = {"inicio": visto_em, "links": len(links), "novos": len(novos), "inicial": inicial}
    if not links:
        titulo = (page_cat.title() or "")[:80]
        reg["bloqueio"] = f"nenhum anúncio na página (título: {titulo!r})"
        return reg
    futuros = []
    for u in novos:
        iid = id_do_link(u)
        vistos.add(iid)
        if inicial:
            # 1º ciclo: o que já estava no ar quando o robô ligou não entra na medição
            gravar(VISTOS, {"id": iid, "url": u, "visto_em": visto_em, "inicial": True})
            continue
        try:
            item = extract_item(page_item, u)  # o navegador é um só: coleta em fila
        except Exception as e:
            gravar(VISTOS, {"id": iid, "url": u, "visto_em": visto_em, "erro": str(e)[:200]})
            continue
        linha = {"id": iid, "url": u, "visto_em": visto_em, "coletado_em": item.get("coletado_em"),
                 "upload": item.get("upload"), "titulo": item.get("titulo"), "preco": item.get("preco"),
                 "tamanho": item.get("tamanho"), "marca": item.get("marca")}
        if CLASSIFICAR and item.get("fotos") and recente(item):
            futuros.append(pool.submit(classificar_linha, linha, item, t_visto))  # IA em paralelo
        else:
            linha["classificado"] = False
            gravar(VISTOS, linha)
            log(f"novo {iid} | {linha.get('upload')} | sem IA (antigo) | {(linha.get('titulo') or '')[:50]}")
    for f in as_completed(futuros):
        linha = f.result()
        gravar(VISTOS, linha)
        log(f"novo {linha['id']} | {linha.get('upload')} | {linha.get('decisao')} em {linha['segundos_ate_decisao']}s "
            f"| {(linha.get('titulo') or '')[:50]}")
    reg["duracao_s"] = round(time.time() - t0, 1)
    return reg


def main() -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    vistos = carregar_vistos()
    inicial = not vistos
    log(f"modo sombra: intervalo {INTERVALO}s, classificar={CLASSIFICAR}, {len(vistos)} ids já vistos, dados em {DIR}")
    falhas = 0
    with sync_playwright() as p, ThreadPoolExecutor(WORKERS) as pool:
        while True:
            browser, context, page_cat = abrir_sessao_vinted(p)
            page_item = context.new_page()
            sessao_desde = time.time()
            try:
                while time.time() - sessao_desde < RENOVAR_SESSAO_H * 3600:
                    try:
                        reg = ciclo(page_cat, page_item, vistos, inicial, pool)
                        inicial = False
                    except Exception as e:
                        reg = {"inicio": agora(), "erro": f"{type(e).__name__}: {str(e)[:200]}"}
                        traceback.print_exc()
                    gravar(CICLOS, reg)
                    if reg.get("bloqueio") or reg.get("erro"):
                        falhas += 1
                        espera = min(900, INTERVALO * 2 ** min(falhas, 4))
                        log(f"problema ({reg.get('bloqueio') or reg.get('erro')}) — esperando {espera}s")
                        time.sleep(espera)
                        if falhas >= 3:
                            break  # sessão nova
                        continue
                    falhas = 0
                    time.sleep(INTERVALO + random.uniform(-10, 10))
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
            log("renovando a sessão do navegador")


if __name__ == "__main__":
    main()
