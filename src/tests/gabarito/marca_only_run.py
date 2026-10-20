"""Roda SÓ o portão de marca (+ recheck 4o) sobre uma rodada base, sem a cascata cara.
Itens que passam a passar no portão ganham os agentes downstream; os que passam a ser
barrados perdem. Uso: python -m src.tests.gabarito.marca_only_run --dataset D --base L --label L2"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from .gabarito_run import _arg, _montar_inputs, _carregar_rodada, REG
from .gabarito_run_sundek import _processar, _hashes_atuais, ORDEM, DOWNSTREAM, CRITERIOS

ds = _arg("--dataset"); base_l = _arg("--base"); label = _arg("--label")
base = _carregar_rodada(base_l); assert base and base["dataset"] == ds
inputs = _montar_inputs(ds)
res, tok = {}, [0, 0]
mudou = []

def tarefa(it):
    b = base["itens"].get(it["id"]) or {}
    out, i1, o1 = _processar(it, {"marca"}, b)
    if b.get("_gate") and not out.get("_gate"):   # passou a passar → roda downstream
        b2 = {**out, "_gate": None}
        out2, i2, o2 = _processar(it, set(ORDEM) - {"marca"}, b2)
        out2["e_sundek"], out2["e_short"] = out["e_sundek"], out["e_short"]
        out, i1, o1 = out2, i1 + i2, o1 + o2
    return it["id"], out, i1, o1, b.get("_gate"), out.get("_gate"), b.get("e_sundek")

with ThreadPoolExecutor(3) as ex:
    for iid, out, i1, o1, g0, g1, e0 in ex.map(tarefa, inputs):
        res[iid] = out; tok[0] += i1; tok[1] += o1
        if g0 != g1 or e0 != out.get("e_sundek"):
            mudou.append((iid, e0, out.get("e_sundek"), g0, g1))
(REG / f"rodada-{label}.json").write_text(json.dumps({
    "label": label, "dataset": ds, "gerado_em": datetime.now(timezone.utc).isoformat(),
    "base": base_l, "agentes_rodados": ["marca(+downstream nos que mudaram de portão)"],
    "prompt_hashes": _hashes_atuais(), "tokens_in": tok[0], "tokens_out": tok[1],
    "itens": res}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"OK {label}: {len(res)} itens; mudaram e_sundek/portão: {mudou}")
