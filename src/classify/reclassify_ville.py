"""Reclassifica UMA etapa da Vilebrequin sem re-rodar o pipeline inteiro.

Lê data/coleta-ville-classificada.json, refaz a etapa pedida e recalcula o score.
Espelha os reclassify_* do Sundek.

Uso:
  python -m src.classify.reclassify_ville                 # só recalcula o SCORE (sem IA, grátis)
  python -m src.classify.reclassify_ville --etapa cor     # refaz cor + score
  python -m src.classify.reclassify_ville --etapa tartaruga --workers 8
  python -m src.classify.reclassify_ville --etapa autenticidade
  python -m src.classify.reclassify_ville --id 8940219584 # só um item (todas as etapas de IA)

Etapas: score (default) | cor | tartaruga | autenticidade
Quando usar: você mexeu no prompt/regra de UMA etapa e quer o efeito sem
repagar o pipeline todo. O score é sempre recalculado no fim.
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Console do Windows é cp1252 e quebra em ✓/✗/🐢 — força UTF-8 na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .tartaruga import classificar_tartaruga
from .autenticidade_ville import verificar_autenticidade
from .cor import classificar_cor
from .score_ville import calcular_score

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-ville-classificada.json"

_lock = threading.Lock()


def _arg(nome: str, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _refazer_etapa(item: dict, etapa: str) -> dict:
    """Refaz a etapa de IA pedida no item (in-place no dict) e devolve."""
    tipo = (item.get("classificacao") or {}).get("tipo")
    # Só faz sentido rodar IA em itens que chegaram à classificação de padrão.
    if tipo in (None, "erro", "nao_ville", "nao_vilebrequin", "nao_short"):
        return item

    if etapa == "tartaruga":
        t = classificar_tartaruga(item)
        t.pop("_usage", None)
        item["tartaruga"] = t
        item["classificacao"] = {**(item.get("classificacao") or {}), "tipo": t.get("tipo", "indefinido")}
    elif etapa == "cor":
        c = classificar_cor(item)
        c.pop("_usage", None)
        item["cor"] = c
    elif etapa == "autenticidade":
        tipo_tart = (item.get("tartaruga") or {}).get("tipo")
        if tipo_tart in ("liso", "indefinido", None):
            item["autenticidade"] = {"autenticidade": "indefinido",
                                     "evidencia": "liso/indefinido — sem padrão de referência"}
        else:
            a = verificar_autenticidade(item)
            a.pop("_usage", None)
            item["autenticidade"] = a
        item["classificacao"] = {**(item.get("classificacao") or {}),
                                 "autenticidade": item["autenticidade"].get("autenticidade")}
    return item


def main() -> None:
    if not PATH.exists():
        print("coleta-ville-classificada.json não encontrado. Rode `python -m src.classify.ville_run`.")
        sys.exit(1)

    etapa = _arg("--etapa", "score")
    workers = int(_arg("--workers", "4"))
    only_id = _arg("--id")

    itens = json.loads(PATH.read_text(encoding="utf-8"))
    alvos = [it for it in itens if (not only_id or str(it.get("id")) == str(only_id))]

    if etapa == "score":
        # Sem IA: só recalcula a decisão de compra em cima do que já está classificado.
        n = 0
        for it in alvos:
            it["score"] = calcular_score(it)
            n += 1
        PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Score recalculado em {n} itens (sem custo de IA).")
        _resumo(itens)
        return

    if etapa not in ("cor", "tartaruga", "autenticidade"):
        print(f"Etapa inválida: {etapa}. Use: score | cor | tartaruga | autenticidade")
        sys.exit(1)

    print(f"=== Reclassify Ville · etapa={etapa} · {len(alvos)} itens · {workers} workers ===\n")
    feito = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_refazer_etapa, it, etapa): it for it in alvos}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"  erro no item {it.get('id')}: {e}")
            it["score"] = calcular_score(it)
            with _lock:
                feito += 1
                if feito % 20 == 0:
                    PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"  {feito}/{len(alvos)} (checkpoint salvo)")

    PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOK — {feito} itens reprocessados (etapa {etapa}) + score recalculado.")
    _resumo(itens)


def _resumo(itens: list) -> None:
    dec = lambda d: sum(1 for x in itens if (x.get("score") or {}).get("decisao") == d)
    print(f"  ✓ Compráveis: {dec('compravel')} · ~ Médios: {dec('medio')} · ✗ Descartados: {dec('descartado')}")


if __name__ == "__main__":
    main()
