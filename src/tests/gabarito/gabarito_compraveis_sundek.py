"""Roda o pipeline SUNDEK UMA VEZ nos 43 shorts compráveis (fotos locais, sem Vinted)
e regenera votacao/public/gabarito_compraveis_sundek.json preenchendo o campo "ia".

⚠ OPCIONAL — GASTA IA. A tela /gabarito-ia-compraveis-sundek é "às cegas": ela NÃO
mostra o palpite da IA (o humano responde sem ver). Este script só existe pra, se um
dia se quiser, ter a resposta da IA gravada no JSON e comparar com o gabarito humano
(via gabarito_diff_sundek / gabarito_aval_sundek). Rodar NÃO muda a tela às cegas —
ela ignora o campo "ia" de qualquer jeito; só popula o dado pra métrica.

Espelha o gabarito_compraveis_ville.py, mas importa o pipeline Sundek
(gabarito_run_sundek) e seus 14 critérios. Como não há dado do Vinted, classifica
do zero com a IA. Reusa o _processar do harness (mesmo gating/critérios da produção,
sem os short-circuits de custo).

Uso (com o python do venv, precisa OPENAI_API_KEY no .env):
  .venv/Scripts/python -m src.tests.gabarito.gabarito_compraveis_sundek
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

from .gabarito_run_sundek import _processar, ORDEM, CRITERIOS

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "votacao" / "public"
ITENS = DATA / "compraveis_sundek_itens.json"
OUT = PUBLIC / "gabarito_compraveis_sundek.json"

# Título "hint" só pra ajudar o double-check da marca (a decisão real é por visão).
TITULO = "Sundek short de banho"

_lock = threading.Lock()


def main() -> None:
    if not ITENS.exists():
        print("compraveis_sundek_itens.json não encontrado (rode a cópia das fotos antes).")
        sys.exit(1)
    itens = json.loads(ITENS.read_text(encoding="utf-8"))
    total = len(itens)
    print(f"=== Compráveis Sundek · classificando {total} shorts (2 fotos cada) ===\n")

    resultados: dict[str, dict] = {}
    in_tok = out_tok = 0
    t0 = time.time()

    def tarefa(it):
        item = {
            "id": it["id"], "titulo": TITULO, "cor": None,
            "tamanho": None, "estado": None, "fotos_local": it["fotos"],
        }
        try:
            # set(ORDEM) = roda todos os agentes; base=None = sem baseline pra copiar.
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
                tag = f"ERRO({err[:40]})" if err else f"sundek={crit.get('e_sundek')}·tipo={crit.get('tipo')}·listra={crit.get('listra')}·cor={crit.get('cor_tier')}"
                print(f"  [{feito:02d}/{total}] {iid} → {tag}", flush=True)

    # Monta o JSON no MESMO formato que a tela lê (igual ao gabarito_compraveis_ville.json).
    saida = []
    for it in itens:
        iid = it["id"]
        crit = resultados.get(iid, {})
        ia = {k: crit.get(k) for k in CRITERIOS}
        saida.append({
            "id": iid,
            "url": None,
            "titulo": "Sundek (comprável)",
            "tamanho": None,
            "estado": None,
            "preco": None,
            "bucket": "comprável",
            "fotos": it["fotos"],
            "ia": ia,
        })

    doc = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "fotos locais (CompráveisSundekDidier) — classificado pela IA",
        "total": len(saida),
        "itens": saida,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    custo = (in_tok / 1_000_000) * 0.15 + (out_tok / 1_000_000) * 0.60  # maioria é mini
    print(f"\nOK -> {OUT} ({len(saida)} itens)")
    print(f"  tokens in/out: {in_tok:,}/{out_tok:,} · custo aprox: ${custo:.3f} · {time.time()-t0:.1f}s")
    print("  (A tela segue às cegas — o campo 'ia' agora populado só serve pra métrica/diff.)")


if __name__ == "__main__":
    main()
