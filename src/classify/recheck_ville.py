"""Recheck COMPLETO dos candidatos Ville (compravel/medio) — antes de mandar pro cliente.

Re-roda TODAS as etapas de IA sobre os candidatos, em ordem de pipeline:
  marca → tartaruga → autenticidade → cor → cordao
recalculando o score após cada etapa. A cada etapa re-filtra pelos candidatos
ATUAIS, então um item reprovado numa etapa não gasta IA nas seguintes.

No fim, regenera:
  - data/analise-ville.html
  - votacao/public/items.json  (preservando os itens Sundek congelados, já que a
    fonte Sundek está zerada e seriam perdidos numa regeneração normal)

Uso:
  python -m src.classify.recheck_ville              # 6 workers
  python -m src.classify.recheck_ville --workers 8
"""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Console do Windows é cp1252 e quebra em ✓/✗/🐢 — força UTF-8 na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .reclassify_ville import _refazer_etapa, _arg
from .score_ville import calcular_score
from ..build import analise_ville
from ..build import votacao_items

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-ville-classificada.json"

# Ordem de pipeline. marca primeiro (pode reprovar marca/sem_evidencia), depois
# o padrão (tartaruga), o bolso (autenticidade), e os atributos (cor, cordao).
ETAPAS = ["marca", "tartaruga", "autenticidade", "cor", "cordao"]


def _e_candidato(item: dict) -> bool:
    return (item.get("score") or {}).get("decisao") in ("compravel", "medio")


def main() -> None:
    if not PATH.exists():
        print("coleta-ville-classificada.json não encontrado.")
        sys.exit(1)

    workers = int(_arg("--workers", "6"))
    itens = json.loads(PATH.read_text(encoding="utf-8"))

    cand0 = [x for x in itens if _e_candidato(x)]
    print(f"=== Recheck completo · {len(cand0)} candidatos · etapas: {', '.join(ETAPAS)} ===")

    for etapa in ETAPAS:
        alvos = [x for x in itens if _e_candidato(x)]
        print(f"\n--- etapa {etapa} · {len(alvos)} candidatos ---")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_refazer_etapa, it, etapa): it for it in alvos}
            feito = 0
            for fut in as_completed(futs):
                it = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"  erro no item {it.get('id')}: {e}")
                it["score"] = calcular_score(it)
                feito += 1
        # salva após cada etapa (checkpoint)
        PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
        dec = Counter((x.get("score") or {}).get("decisao") for x in itens)
        print(f"  → compráveis={dec['compravel']} médios={dec['medio']} descartados={dec['descartado']}")

    # ── Regenera relatório + items.json preservando Sundek congelado ──────
    print("\n--- regenerando analise-ville.html ---")
    analise_ville.main()

    print("--- regenerando items.json (preservando Sundek congelado) ---")
    out_path = votacao_items.OUT
    cur = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    sundek_frozen = [x for x in cur if x.get("marca") == "sundek"]
    ville = votacao_items._carregar(PATH, "vilebrequin")
    ids = {x["id"] for x in ville}
    merged = ville + [x for x in sundek_frozen if x["id"] not in ids]
    merged.sort(key=lambda x: (0 if x["decisao"] == "compravel" else 1, -x["score"]))
    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

    n_v = sum(1 for x in merged if x["marca"] == "vilebrequin")
    n_s = sum(1 for x in merged if x["marca"] == "sundek")
    print(f"\nOK — items.json: {len(merged)} itens ({n_v} Ville + {n_s} Sundek congelados).")
    print("Revise em data/analise-ville.html antes de mandar pro cliente.")


if __name__ == "__main__":
    main()
