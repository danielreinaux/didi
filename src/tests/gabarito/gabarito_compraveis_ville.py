"""Roda o pipeline Ville UMA VEZ nos 40 shorts compráveis (fotos locais, sem Vinted)
e gera votacao/public/gabarito_compraveis_ville.json pra tela /gabarito-ia-compraveis-ville.

Diferente do gabarito_ville.py (que lê respostas cacheadas da coleta), aqui NÃO
temos dado do Vinted — então classificamos do zero com a IA. Reusa o _processar
do harness (mesmo gating/critérios).

Uso (com o python do venv, precisa OPENAI_API_KEY no .env):
  .venv/Scripts/python -m src.tests.gabarito.gabarito_compraveis_ville
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .gabarito_run import _processar, ORDEM, CRITERIOS

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "votacao" / "public"
ITENS = DATA / "compraveis_ville_itens.json"
OUT = PUBLIC / "gabarito_compraveis_ville.json"

# Título "hint" só pra passar do prefilter de título (a decisão real é por visão).
TITULO = "Vilebrequin short de banho tartaruga"

_lock = threading.Lock()


def main() -> None:
    if not ITENS.exists():
        print("compraveis_ville_itens.json não encontrado (rode a cópia das fotos antes).")
        sys.exit(1)
    itens = json.loads(ITENS.read_text(encoding="utf-8"))
    total = len(itens)
    print(f"=== Compráveis Ville · classificando {total} shorts (2 fotos cada) ===\n")

    resultados: dict[str, dict] = {}
    in_tok = out_tok = 0
    t0 = time.time()

    def tarefa(it):
        item = {
            "id": it["id"], "titulo": TITULO, "cor": None,
            "tamanho": None, "estado": None, "fotos_local": it["fotos"],
        }
        try:
            crit, i_t, o_t = _processar(item, set(ORDEM), None)
            return it["id"], crit, i_t, o_t, None
        except Exception as e:
            return it["id"], {c: None for c in CRITERIOS}, 0, 0, str(e)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(tarefa, it) for it in itens]
        feito = 0
        for fut in as_completed(futs):
            iid, crit, i_t, o_t, err = fut.result()
            resultados[iid] = crit
            with _lock:
                in_tok += i_t
                out_tok += o_t
                feito += 1
                tag = f"ERRO({err[:40]})" if err else f"{crit.get('tipo')}·auth={crit.get('autenticidade')}·cor={crit.get('cor_bucket')}·fecho={crit.get('fecho')}"
                print(f"  [{feito:02d}/{total}] {iid} → {tag}", flush=True)

    # Monta o JSON no formato que a tela lê (igual ao gabarito_ville.json).
    saida = []
    for it in itens:
        iid = it["id"]
        crit = resultados.get(iid, {})
        ia = {k: crit.get(k) for k in CRITERIOS}
        saida.append({
            "id": iid,
            "url": None,
            "titulo": "Vilebrequin (comprável)",
            "tamanho": None,
            "estado": None,
            "preco": None,
            "bucket": "comprável",
            "fotos": it["fotos"],
            "ia": ia,
        })

    doc = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "fotos locais (CompráveisVilleDidi) — classificado pela IA",
        "total": len(saida),
        "itens": saida,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    custo = (in_tok / 1_000_000) * 2.5 + (out_tok / 1_000_000) * 10  # maioria é gpt-4o
    print(f"\nOK -> {OUT} ({len(saida)} itens)")
    print(f"  tokens in/out: {in_tok:,}/{out_tok:,} · custo aprox: ${custo:.3f} · {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
