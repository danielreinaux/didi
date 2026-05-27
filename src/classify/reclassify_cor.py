"""Re-roda APENAS a etapa de cor sobre itens já classificados.

Útil quando o prompt de cor (`src/prompts/cor_tier.py`) foi alterado e você quer
ver o impacto sem refazer o pipeline inteiro (que é mais caro).

Roda em paralelo, salva checkpoint a cada 30 itens, recalcula `tier_final`
via `avaliar_combo` e recalcula o `score` no final.

Filtros (selecione um ou combine):
  --apenas-tier TIER   Só itens com cor.tier == TIER (ex: ruim, ok, boa).
                       Pode ser passado várias vezes: --apenas-tier ruim --apenas-tier ok
  --todos-lisos        Refaz cor em todos os lisos (cuidado: ~600 itens = ~$5).
  --id ID              Só esse item específico. Pode repetir.

Sem nenhum filtro o padrão é --apenas-tier ruim (uso mais comum).

Uso:
  python -m src.classify.reclassify_cor                          # só ruim
  python -m src.classify.reclassify_cor --apenas-tier ok
  python -m src.classify.reclassify_cor --todos-lisos --workers 12
  python -m src.classify.reclassify_cor --id 8909677285
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .cor import classificar_cor
from ..utils.listra_tier import avaliar_combo

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-classificada.json"

_lock = threading.Lock()


def _log(msg: str) -> None:
    with _lock:
        print(msg, flush=True)


def _save_atomic(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _parse_args(argv: list[str]) -> dict:
    args = {
        "workers": 8,
        "tiers": [],
        "ids": [],
        "todos_lisos": False,
        "path": PATH,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--workers" and i + 1 < len(argv):
            args["workers"] = int(argv[i + 1]); i += 2
        elif a == "--apenas-tier" and i + 1 < len(argv):
            args["tiers"].append(argv[i + 1]); i += 2
        elif a == "--id" and i + 1 < len(argv):
            args["ids"].append(argv[i + 1]); i += 2
        elif a == "--todos-lisos":
            args["todos_lisos"] = True; i += 1
        elif a == "--path" and i + 1 < len(argv):
            args["path"] = Path(argv[i + 1]); i += 2
        else:
            print(f"Argumento desconhecido: {a}"); sys.exit(2)
    # default
    if not args["tiers"] and not args["ids"] and not args["todos_lisos"]:
        args["tiers"] = ["ruim"]
    return args


def _selecionar(todos: list[dict], args: dict) -> list[tuple[int, dict]]:
    alvos = []
    for i, item in enumerate(todos):
        cl = item.get("classificacao") or {}
        cor = item.get("cor") if isinstance(item.get("cor"), dict) else {}
        if args["ids"] and item.get("id") in args["ids"]:
            alvos.append((i, item)); continue
        if args["todos_lisos"] and cl.get("tipo") == "liso":
            alvos.append((i, item)); continue
        if args["tiers"] and cor.get("tier") in args["tiers"]:
            alvos.append((i, item)); continue
    return alvos


def _processar(item: dict, idx: int, total: int) -> dict:
    titulo = (item.get("titulo") or "")[:40]
    prefix = f"  [{idx}/{total}] {titulo}"
    cor_antes = item.get("cor") if isinstance(item.get("cor"), dict) else {}
    tier_antes = cor_antes.get("tier", "?")

    try:
        novo = classificar_cor(item)
        novo.pop("_usage", None)

        cor_atual = dict(cor_antes)  # preserva campos como cores_listras
        cor_atual["cor_principal"] = novo.get("cor_principal", cor_atual.get("cor_principal"))
        cor_atual["tier"] = novo.get("tier")
        cor_atual["justificativa"] = novo.get("justificativa", "")
        if "neon_ou_metalico" in novo:
            cor_atual["neon_ou_metalico"] = novo["neon_ou_metalico"]

        # Recalcula tier_final via combo cor+listras
        cores_listras = cor_atual.get("cores_listras") or []
        combo = avaliar_combo(cor_atual["cor_principal"], cores_listras, cor_atual["tier"])
        cor_atual["listra_tier"] = combo["listra_tier"]
        cor_atual["tier_final"] = combo["tier_final"]
        cor_atual["combo_motivo"] = combo["motivo"]

        flecha = "→" if tier_antes != cor_atual["tier"] else "="
        _log(
            f"{prefix} | {cor_atual['cor_principal']:<18} "
            f"{tier_antes}{flecha}{cor_atual['tier']} "
            f"(final={cor_atual['tier_final']})"
        )
        return {**item, "cor": cor_atual}

    except Exception as e:
        _log(f"{prefix} → ERRO: {str(e)[:80]}")
        return item


def main() -> None:
    args = _parse_args(sys.argv[1:])
    path = args["path"]

    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)

    todos = json.loads(path.read_text(encoding="utf-8"))
    alvos = _selecionar(todos, args)

    if not alvos:
        print("Nenhum item bate com os filtros.")
        sys.exit(0)

    filtro_desc = []
    if args["ids"]: filtro_desc.append(f"ids={args['ids']}")
    if args["tiers"]: filtro_desc.append(f"tiers={args['tiers']}")
    if args["todos_lisos"]: filtro_desc.append("todos-lisos")
    print(f"Reclassificando cor em {len(alvos)} itens ({', '.join(filtro_desc)}) com {args['workers']} workers...\n")

    resultados: dict[int, dict] = {}

    with ThreadPoolExecutor(max_workers=args["workers"]) as ex:
        futures = {ex.submit(_processar, item, n + 1, len(alvos)): orig_i
                   for n, (orig_i, item) in enumerate(alvos)}
        for fut in as_completed(futures):
            orig_i = futures[fut]
            try:
                resultados[orig_i] = fut.result()
            except Exception as e:
                _log(f"  ERRO futuro: {e}")

            if len(resultados) % 5 == 0:
                out = list(todos)
                for idx, r in resultados.items():
                    out[idx] = r
                with _lock:
                    _save_atomic(path, out)
                _log(f"\n  💾 Checkpoint: {len(resultados)}/{len(alvos)}\n")

    # Persiste resultado final (atomico)
    out = list(todos)
    for idx, r in resultados.items():
        out[idx] = r
    _save_atomic(path, out)

    # Recalcula scores (tier_final mudou)
    from .score import calcular_score
    todos_final = json.loads(path.read_text(encoding="utf-8"))
    for it in todos_final:
        if not it.get("manual_exclusao"):
            it["score"] = calcular_score(it)
    _save_atomic(path, todos_final)

    # Stats
    from collections import Counter
    novos_tiers = Counter()
    mudancas = Counter()  # (antes -> depois)
    for orig_i, r in resultados.items():
        antes = (todos[orig_i].get("cor") or {})
        antes_t = antes.get("tier", "?") if isinstance(antes, dict) else "?"
        depois = r.get("cor", {}) or {}
        depois_t = depois.get("tier", "?")
        novos_tiers[depois_t] += 1
        if antes_t != depois_t:
            mudancas[f"{antes_t} → {depois_t}"] += 1

    decisoes = Counter((it.get("score") or {}).get("decisao", "") for it in todos_final)

    print(f"\n✅ Concluído: {len(resultados)} itens reprocessados")
    print(f"   Distribuição novos tiers: {dict(novos_tiers)}")
    if mudancas:
        print(f"   Mudanças de tier:")
        for k, v in mudancas.most_common():
            print(f"     {k}: {v}")
    print(f"\n   Comprável: {decisoes['compravel']} | Médio: {decisoes['medio']} | Descartado: {decisoes['descartado']}")
    print(f"   Salvo em {path}")


if __name__ == "__main__":
    main()
