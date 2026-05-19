"""Re-roda liso/estampado + elastico nos lisos para capturar:
  - cores_listras, tecido_brilhoso, tem_bolso_frontal  (liso/estampado)
  - tipo_fechamento  (elastico)
  - tier_final  (listra_tier combo)

Uso: python -m src.reclassify_listras [--workers N]
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .classify import classificar_item
from .classify_elastico import verificar_elastico
from .listra_tier import avaliar_combo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-classificada.json"

_lock = threading.Lock()


def _log(msg: str) -> None:
    with _lock:
        print(msg, flush=True)


def _processar(item: dict, idx: int, total: int) -> dict:
    titulo = (item.get("titulo") or "")[:40]
    prefix = f"  [{idx}/{total}] {titulo}"

    try:
        # 1. Reclassifica liso/estampado — captura novos campos
        c = classificar_item(item)
        c.pop("_usage", None)

        cores_listras = c.get("cores_listras") or []
        tecido_brilhoso = c.get("tecido_brilhoso", False)
        tem_bolso_frontal = c.get("tem_bolso_frontal", False)
        listra_na_frente = c.get("listra_na_frente", False)
        tem_bolso_traseiro = c.get("tem_bolso_traseiro", None)

        cl_atual = item.get("classificacao") or {}
        cl_atual["cores_listras"] = cores_listras
        cl_atual["tem_listra_lateral_sundek"] = c.get("tem_listra_lateral_sundek", cl_atual.get("tem_listra_lateral_sundek"))
        cl_atual["tecido_brilhoso"] = tecido_brilhoso
        cl_atual["tem_bolso_frontal"] = tem_bolso_frontal
        cl_atual["listra_na_frente"] = listra_na_frente
        cl_atual["tem_bolso_traseiro"] = tem_bolso_traseiro

        # 2. Reclassifica elastico — captura tipo_fechamento
        el = verificar_elastico(item)
        el.pop("_usage", None)

        # 3. Recalcula combo tier
        cor_atual = item.get("cor") or {}
        if not isinstance(cor_atual, dict):
            cor_atual = {}
        tier_ia = cor_atual.get("tier", "ok")
        cor_nome = cor_atual.get("cor_principal", "")
        combo = avaliar_combo(cor_nome, cores_listras, tier_ia)
        cor_atual["cores_listras"] = cores_listras
        cor_atual["listra_tier"] = combo["listra_tier"]
        cor_atual["tier_final"] = combo["tier_final"]
        cor_atual["combo_motivo"] = combo["motivo"]

        tipo_fechamento = el.get("tipo_fechamento", "indefinido")
        flags = []
        if tecido_brilhoso: flags.append("brilhoso!")
        if tem_bolso_frontal: flags.append("bolso_frontal!")
        if listra_na_frente: flags.append("listra_frente!")
        if tem_bolso_traseiro is False: flags.append("sem_bolso_traseiro!")
        if tipo_fechamento in ("botao", "velcro"): flags.append(f"{tipo_fechamento}!")
        flag_str = f" ⚠ {', '.join(flags)}" if flags else ""

        _log(f"{prefix} → listras={cores_listras} {tier_ia}→{combo['tier_final']} fecho={tipo_fechamento}{flag_str}")

        return {**item, "classificacao": cl_atual, "cor": cor_atual, "elastico": el}

    except Exception as e:
        _log(f"{prefix} → ERRO: {str(e)[:80]}")
        return item


def main() -> None:
    workers = 8
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--workers" and i + 1 < len(sys.argv[1:]):
            workers = int(sys.argv[i + 2])

    todos = json.loads(PATH.read_text())
    lisos = [(i, item) for i, item in enumerate(todos)
             if (item.get("classificacao") or {}).get("tipo") == "liso"]

    print(f"Re-classificando listras em {len(lisos)} lisos com {workers} workers...\n")

    resultados: dict[int, dict] = {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_processar, item, n + 1, len(lisos)): i
                   for n, (i, item) in enumerate(lisos)}
        for fut in as_completed(futures):
            orig_i = futures[fut]
            try:
                resultados[orig_i] = fut.result()
            except Exception as e:
                _log(f"  ERRO futuro: {e}")

            # Salva a cada 30
            if len(resultados) % 30 == 0:
                out = list(todos)
                for idx, r in resultados.items():
                    out[idx] = r
                with _lock:
                    PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))
                _log(f"\n  💾 Checkpoint: {len(resultados)}/{len(lisos)}\n")

    # Salva final
    out = list(todos)
    for idx, r in resultados.items():
        out[idx] = r
    PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # Stats
    salvos = sum(1 for r in resultados.values() if (r.get("cor") or {}).get("listra_tier") == "salva")
    brilhosos = sum(1 for r in resultados.values() if (r.get("classificacao") or {}).get("tecido_brilhoso"))
    bolso_frontal = sum(1 for r in resultados.values() if (r.get("classificacao") or {}).get("tem_bolso_frontal"))
    botoes = sum(1 for r in resultados.values() if (r.get("elastico") or {}).get("tipo_fechamento") in ("botao","velcro"))

    # Recalcula scores
    from .score import calcular_score
    todos_final = json.loads(PATH.read_text())
    for it in todos_final:
        it["score"] = calcular_score(it)
    PATH.write_text(json.dumps(todos_final, indent=2, ensure_ascii=False))

    from collections import Counter
    decisoes = Counter((it.get("score") or {}).get("decisao","") for it in todos_final)

    print(f"\n✅ Concluído: {len(lisos)} lisos reprocessados")
    print(f"   Listras que salvam cor: {salvos}")
    print(f"   Tecido brilhoso (excluídos): {brilhosos}")
    print(f"   Bolso frontal (excluídos): {bolso_frontal}")
    print(f"   Botão/velcro (excluídos): {botoes}")
    print(f"\n   Comprável: {decisoes['compravel']} | Médio: {decisoes['medio']} | Descartado: {decisoes['descartado']}")
    print(f"   Salvo em {PATH}")


if __name__ == "__main__":
    main()
