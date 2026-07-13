"""Comparativo gpt-4o × gpt-4o-mini CRUZANDO os 4 datasets num HTML só.

Diferente do modeltest/run.py (um dataset por vez, modelos em coluna), aqui os
MODELOS são fixos — gpt-4o (referência) vs gpt-4o-mini (candidato) — e as COLUNAS
são os 4 datasets. Cada dataset vira 3 sub-colunas: 4o | mini | Δ (mini − 4o).
Linhas = critérios de cada pipeline: critério do pipeline Ville aparece só nas 2
colunas Ville (Ville / Ville compráveis) e some nas 2 do Sundek, e vice-versa —
é o "regra diferente → vazio numa, preenchido noutra".

Δ verde = o mini IGUALOU ou SUPEROU o 4o naquele critério+dataset (dá pra baixar
pro mini ali). Δ vermelho = o mini regrediu (precisa do 4o).

Fluxo:
  # 0) atualizar a verdade humana (inclui gabaritos recém-fechados, ex: Sundek compráveis):
  python -m src.tests.gabarito.gabarito_export

  # 1) validar só o FORMATO, sem gastar IA (números fabricados no MESMO template):
  python -m src.tests.modeltest.run_datasets --mock

  # 2) rodar de verdade (2 modelos × 4 datasets):
  python -m src.tests.modeltest.run_datasets --limit 6   # smoke test barato primeiro
  python -m src.tests.modeltest.run_datasets             # completo
  python -m src.tests.modeltest.run_datasets --workers 4

Saída (tudo numa pasta só, isolada do modeltest/run.py antigo):
  data/modeltest/4datasets/comparativo-datasets.html   ← abra este
  data/modeltest/4datasets/comparativo-datasets.json
  data/modeltest/4datasets/cruas/<dataset>__<modelo>.json  ← respostas cruas da IA
"""
import argparse
import json
import threading
import time
from html import escape
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from ...config import IA as CONFIG_IA
# Pipeline Ville (10 critérios) + Sundek (14 critérios) — reaproveitados inteiros.
from ..gabarito import gabarito_run as gr
from ..gabarito import gabarito_run_sundek as grs
from ..gabarito.gabarito_diff import (
    _norm, _graded, CRITERIOS as CRIT_V, LABELS as LAB_V, _item_100 as _item100_v,
)
from ..gabarito.gabarito_aval_sundek import (
    CRITERIOS as CRIT_S, LABELS as LAB_S, _aplica, _item_100 as _item100_s,
)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = ROOT / "data"
# Tudo deste script mora numa subpasta própria — não mistura com o comparativo-ville.*
# do modeltest/run.py, e não toca no data/regressao/ (que é só leitura da verdade).
OUT_DIR = DATA / "modeltest" / "4datasets"
TRUTH_PATH = DATA / "regressao" / "gabarito_respostas.json"
USD_BRL = 5.0

MODELOS = ["gpt-4o", "gpt-4o-mini"]   # [referência, candidato]
REF, CAND = MODELOS

# Preço OpenAI (USD/1M tokens) — jul/2026. (Espelha o modeltest/run.py.)
PRECOS = {
    "gpt-4o":      {"in": 2.50, "out": 10.00},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
}

# Os 4 datasets, na ordem das colunas: bloco Ville, depois bloco Sundek.
# (chave do gabarito_<chave>.json, rótulo da coluna, família = qual pipeline roda)
DATASETS = [
    ("ville",             "Ville",             "ville"),
    ("compraveis_ville",  "Ville compráveis",  "ville"),
    ("sundek",            "Sundek",            "sundek"),
    ("compraveis_sundek", "Sundek compráveis", "sundek"),
]

# Qual modelo cada critério roda HOJE em produção (derivado do config.IA +
# do _track de cada agente em classify/ville_run.py e classify/run.py):
#   config.IA["model"] = gpt-4o-mini · config.IA["model_detalhes"] = gpt-4o
# Ville: marca/tartaruga/autenticidade/fecho → 4o ; cor/cordao/etiqueta → mini.
# Sundek: listra/elastico/bolso → 4o ; marca/tipo/cor/etiqueta → mini
#   (a marca Sundek roda no mini, com re-checagem pontual no 4o quando o título
#    cita "sundek" — ver classify/run.py; aqui marcamos o modelo primário: mini).
HOJE_V = {
    "e_vilebrequin": REF, "e_short": REF, "tipo": REF, "fundo_padrao": REF,
    "aparencia": REF, "autenticidade": REF, "fecho": REF,        # gpt-4o
    "cor_bucket": CAND, "cordao_cor": CAND, "etiqueta": CAND,     # gpt-4o-mini
}
HOJE_S = {
    "listra": REF, "bicolor": REF, "tem_elastico": REF, "fechamento": REF,
    "bolso_traseiro": REF, "bolso_nome": REF, "bolso_frontal": REF,   # gpt-4o
    "e_sundek": CAND, "e_short": CAND, "tipo": CAND, "aparencia": CAND,
    "tecido_brilhoso": CAND, "cor_tier": CAND, "etiqueta": CAND,      # gpt-4o-mini
}

# Por família: (módulo do pipeline, critérios, labels, função _item_100, "graded?",
# modelo de produção por critério)
FAMILIA = {
    "ville":  {"mod": gr,  "crit": CRIT_V, "lab": LAB_V, "cheio": _item100_v,
               "aplica": lambda t, c: _graded(t, c), "hoje": HOJE_V},
    "sundek": {"mod": grs, "crit": CRIT_S, "lab": LAB_S, "cheio": _item100_s,
               "aplica": _aplica, "hoje": HOJE_S},
}


# ─────────────────────────────────────────────────────────────────────────────
# Execução real
# ─────────────────────────────────────────────────────────────────────────────
def _dur(seg: float) -> str:
    """Segundos → "1h05min" / "7min32s" (pra ETA legível)."""
    seg = int(max(0, seg))
    h, m, s = seg // 3600, (seg % 3600) // 60, seg % 60
    return f"{h}h{m:02d}min" if h else f"{m}min{s:02d}s"


class _Prog:
    """Contador GLOBAL de progresso com ETA (thread-safe). Uma 'análise' = 1 short
    passado por 1 modelo — o total é (nº de shorts) × (nº de modelos)."""
    def __init__(self, total: int):
        self.total = total
        self.n = 0
        self.t0 = time.time()
        self._lock = threading.Lock()

    def tick(self, ctx: str, err: str | None = None) -> None:
        with self._lock:
            self.n += 1
            el = time.time() - self.t0
            rest = (self.total - self.n) * (el / self.n) if self.n else 0
            print(f"  ▸ {self.n}/{self.total} shorts analisados · "
                  f"tempo restante estimado ~{_dur(rest)} · {ctx}"
                  + (f"  ⚠ {err}" if err else ""), flush=True)


def _rodar_modelo(fam: dict, inputs: list[dict], modelo: str, workers: int,
                  prog: "_Prog | None" = None, ctx: str = "") -> dict:
    """Roda o pipeline da família inteiro FORÇANDO um modelo. Devolve respostas
    cruas por item + tokens/tempo (os dois modelos são puros → preço 1:1)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    mod = fam["mod"]
    orig = dict(CONFIG_IA)
    CONFIG_IA["model"] = modelo
    CONFIG_IA["model_detalhes"] = modelo
    rodar = set(mod.ORDEM)
    resultados, erros = {}, 0
    tin = tout = 0
    t0 = time.time()

    def processa(inp):
        try:
            out, i, o = mod._processar(inp, rodar, None)
            return inp["id"], out, i, o, None
        except Exception as e:
            return inp["id"], {c: None for c in fam["crit"]}, 0, 0, str(e)[:120]

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(processa, inp) for inp in inputs]
            for k, fut in enumerate(as_completed(futs), 1):
                iid, out, i, o, err = fut.result()
                resultados[iid] = out
                tin += i
                tout += o
                if err:
                    erros += 1
                if prog:
                    prog.tick(f"{ctx} · {modelo}", err)
                else:
                    print(f"    [{modelo}] {k}/{len(inputs)}" + (f"  ⚠ {err}" if err else ""), flush=True)
    finally:
        CONFIG_IA.update(orig)   # restaura o config de produção sempre

    p = PRECOS.get(modelo, {"in": 0.0, "out": 0.0})
    return {
        "itens": resultados, "erros": erros,
        "disponivel": erros < len(inputs),
        "tok_in": tin, "tok_out": tout,
        "custo_usd": (tin / 1e6) * p["in"] + (tout / 1e6) * p["out"],
        "duracao_s": round(time.time() - t0, 1),
    }


def _pontuar(fam: dict, resultados: dict, truth: dict, ids: list[str]) -> dict:
    """Acerto por critério + itens 100% certos, contra a verdade humana."""
    por_crit = {}
    for c in fam["crit"]:
        n = ok = 0
        for iid in ids:
            t = truth[iid]
            if not fam["aplica"](t, c):
                continue
            n += 1
            if _norm(resultados.get(iid, {}).get(c)) == _norm(t.get(c)):
                ok += 1
        por_crit[c] = {"ok": ok, "n": n, "acc": (ok / n * 100) if n else None}

    aval = [i for i in ids if fam["cheio"](resultados.get(i, {}), truth[i]) is not None]
    full = sum(1 for i in aval if fam["cheio"](resultados.get(i, {}), truth[i]))
    return {
        "por_criterio": por_crit, "itens_100": full,
        "itens_avaliaveis": len(aval),
        "pct_100": (full / len(aval) * 100) if aval else None,
    }


def _plano_dataset(chave, rotulo, familia, truth, limit) -> dict:
    """Pré-pass (SEM IA): monta inputs/ids do dataset. Roda antes de tudo pra
    sabermos o TOTAL de shorts — necessário pro ETA global ser correto."""
    ds = {"chave": chave, "rotulo": rotulo, "familia": familia,
          "disponivel": True, "n_itens": 0, "por_modelo": {}, "inputs": [], "ids": []}

    # _dataset_json é genérico (PUBLIC/gabarito_<chave>.json) — vive no gabarito_run.
    if not gr._dataset_json(chave).exists():
        print(f"  ⚠ {chave}: gabarito_{chave}.json não existe — coluna vazia.")
        ds["disponivel"] = False
        return ds

    inputs = gr._montar_inputs(chave)   # genérico (Ville e Sundek usam o mesmo)
    if limit:
        inputs = inputs[:limit]
    ids = [i["id"] for i in inputs
           if i["id"] in truth and isinstance(truth[i["id"]], dict) and truth[i["id"]]]
    ds["n_itens"] = len(ids)
    if not ids:
        print(f"  ⚠ {chave}: nenhum item com verdade humana — coluna vazia. "
              f"(Rode gabarito_export; confira se o gabarito foi preenchido.)")
        ds["disponivel"] = False
        return ds
    ds["inputs"], ds["ids"] = inputs, ids
    return ds


def _rodar_plano(ds: dict, truth: dict, workers: int, prog: _Prog) -> None:
    """Roda os 2 modelos no dataset já planejado, alimentando o progresso global."""
    fam = FAMILIA[ds["familia"]]
    inputs, ids = ds["inputs"], ds["ids"]
    print(f"\n  → {ds['rotulo']} ({ds['chave']}): {len(inputs)} shorts × {len(MODELOS)} modelos")
    for modelo in MODELOS:
        r = _rodar_modelo(fam, inputs, modelo, workers, prog, ctx=ds["rotulo"])
        r["score"] = _pontuar(fam, r["itens"], truth, ids)
        safe = f"{ds['chave']}__{modelo}".replace("/", "_")
        (OUT_DIR / "cruas").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "cruas" / f"{safe}.json").write_text(
            json.dumps(r["itens"], ensure_ascii=False, indent=1), encoding="utf-8")
        ds["por_modelo"][modelo] = r
        s = r["score"]
        print(f"     ✓ {modelo}: 100%={'—' if s['pct_100'] is None else f'{s['pct_100']:.0f}%'} "
              f"· ${r['custo_usd']:.3f} · {r['duracao_s']}s"
              + (f" · ⚠ {r['erros']} erros" if r["erros"] else ""), flush=True)
    # inputs/ids eram só pra rodar/contar — fora do dump final.
    ds.pop("inputs", None)
    ds.pop("ids", None)


# ─────────────────────────────────────────────────────────────────────────────
# Dados fabricados (--mock) — passam pelo MESMO renderizador do run real
# ─────────────────────────────────────────────────────────────────────────────
def _mock() -> list[dict]:
    import random
    random.seed(7)
    n_por_ds = {"ville": 50, "compraveis_ville": 38, "sundek": 50, "compraveis_sundek": 43}
    datasets = []
    for chave, rotulo, familia in DATASETS:
        fam = FAMILIA[familia]
        n = n_por_ds[chave]
        ds = {"chave": chave, "rotulo": rotulo, "familia": familia,
              "disponivel": True, "n_itens": n, "por_modelo": {}}
        # 4o forte; mini geralmente perto, às vezes pior, às vezes empata/supera.
        base_acc = {c: random.randint(72, 99) for c in fam["crit"]}
        for modelo in MODELOS:
            por_crit = {}
            for c in fam["crit"]:
                a = base_acc[c] if modelo == REF else max(30, base_acc[c] + random.randint(-18, 4))
                ok = round(a / 100 * n)
                por_crit[c] = {"ok": ok, "n": n, "acc": ok / n * 100}
            pct = random.randint(24, 42) if modelo == REF else random.randint(12, 40)
            custo = (1.35 if modelo == REF else 0.92) * (n / 50)
            ds["por_modelo"][modelo] = {
                "score": {"por_criterio": por_crit, "itens_100": round(pct / 100 * n),
                          "itens_avaliaveis": n, "pct_100": float(pct)},
                "disponivel": True, "erros": 0,
                "tok_in": int(1_600_000 * n / 50) if modelo == REF else int(6_000_000 * n / 50),
                "tok_out": int(14000 * n / 50), "custo_usd": custo,
                "duracao_s": 250.0 * n / 50,
            }
        datasets.append(ds)
    return datasets


# ─────────────────────────────────────────────────────────────────────────────
# HTML (a matriz cruzada)
# ─────────────────────────────────────────────────────────────────────────────
def _cor_delta(d) -> str:
    if d is None:
        return "#a1a1aa"
    if d >= 1:
        return "#15803d"   # mini igualou/superou → dá pra baixar
    if d <= -1:
        return "#b91c1c"   # mini regrediu
    return "#71717a"       # empate


def _fmt_acc(sc, atual: bool = False) -> str:
    """Célula de acerto de um modelo. atual=True → é o modelo que roda HOJE
    naquele critério (fundo destacado)."""
    cls = "atual" if atual else ""
    if sc is None or sc.get("acc") is None:
        return f'<td class="na {cls}">—</td>'
    return f'<td class="{cls}"><b>{sc["acc"]:.0f}%</b><div class="sub">{sc["ok"]}/{sc["n"]}</div></td>'


def _celulas_criterio(ds: dict, familia: str, c: str) -> str:
    """3 <td> (4o | mini | Δ) do critério c na coluna deste dataset. A sub-coluna
    do modelo que roda HOJE em produção sai destacada."""
    if ds["familia"] != familia:
        return '<td class="off"></td><td class="off"></td><td class="off"></td>'  # não se aplica
    if not ds["disponivel"]:
        return '<td class="nd">—</td><td class="nd">—</td><td class="nd">—</td>'
    hoje = FAMILIA[familia]["hoje"].get(c)   # modelo de produção deste critério
    a = ds["por_modelo"][REF]["score"]["por_criterio"].get(c)
    b = ds["por_modelo"][CAND]["score"]["por_criterio"].get(c)
    aacc = a.get("acc") if a else None
    bacc = b.get("acc") if b else None
    if aacc is None and bacc is None:
        return '<td class="na">—</td><td class="na">—</td><td class="na">—</td>'
    d = (bacc - aacc) if (aacc is not None and bacc is not None) else None
    dtxt = "—" if d is None else f'{"+" if d >= 0 else ""}{d:.0f}'
    return (_fmt_acc(a, atual=(hoje == REF)) + _fmt_acc(b, atual=(hoje == CAND))
            + f'<td class="delta" style="color:{_cor_delta(d)}"><b>{dtxt}</b></td>')


def _badge_hoje(modelo) -> str:
    """Selo no rótulo do critério dizendo qual modelo roda hoje em produção."""
    if modelo == REF:
        return '<span class="hoje h4o">4o hoje</span>'
    if modelo == CAND:
        return '<span class="hoje hmini">mini hoje</span>'
    return ''


def _celulas_resumo(ds: dict, campo: str) -> str:
    """3 <td> (4o | mini | Δ) de uma linha-resumo (itens 100% ou custo)."""
    if not ds["disponivel"]:
        return '<td class="nd">—</td><td class="nd">—</td><td class="nd">—</td>'
    a = ds["por_modelo"][REF]
    b = ds["por_modelo"][CAND]
    if campo == "pct_100":
        av, bv = a["score"]["pct_100"], b["score"]["pct_100"]
        if av is None or bv is None:
            return '<td class="na">—</td><td class="na">—</td><td class="na">—</td>'
        d = bv - av
        return (f'<td><b>{av:.0f}%</b></td><td><b>{bv:.0f}%</b></td>'
                f'<td class="delta" style="color:{_cor_delta(d)}"><b>{"+" if d>=0 else ""}{d:.0f}</b></td>')
    if campo == "custo":
        av, bv = a["custo_usd"] * USD_BRL, b["custo_usd"] * USD_BRL
        d = bv - av  # negativo = mini mais barato (bom) → verde
        cor = "#15803d" if d < -0.001 else ("#b91c1c" if d > 0.001 else "#71717a")
        return (f'<td class="sub2">R$ {av:.2f}</td><td class="sub2">R$ {bv:.2f}</td>'
                f'<td class="delta sub2" style="color:{cor}">{"+" if d>=0 else ""}R$ {d:.2f}</td>')
    return ""


def _html(datasets: list[dict], modo: str) -> str:
    # Cabeçalho: 1 col de critério + 4 grupos de 3 (4o | mini | Δ)
    grp_th = ""
    for ds in datasets:
        sub = (f'{ds["n_itens"]} itens' if ds["disponivel"] else "sem verdade")
        grp_th += f'<th colspan="3" class="grp">{escape(ds["rotulo"])}<div class="sub">{sub}</div></th>'
    sub_th = "".join('<th class="m">4o</th><th class="m">mini</th><th class="m dh">Δ</th>'
                     for _ in datasets)

    # Corpo: seção Ville (critérios do pipeline Ville) + seção Sundek.
    secoes = []
    for familia, titulo in (("ville", "Critérios Ville"), ("sundek", "Critérios Sundek")):
        fam = FAMILIA[familia]
        secoes.append(f'<tr class="sec"><td>{escape(titulo)}</td>'
                      f'<td colspan="{3*len(datasets)}"></td></tr>')
        for c in fam["crit"]:
            badge = _badge_hoje(fam["hoje"].get(c))
            cells = "".join(_celulas_criterio(ds, familia, c) for ds in datasets)
            secoes.append(f'<tr><td class="crit">{escape(fam["lab"].get(c, c))}{badge}</td>{cells}</tr>')

    # Resumos
    r100 = "".join(_celulas_resumo(ds, "pct_100") for ds in datasets)
    rcusto = "".join(_celulas_resumo(ds, "custo") for ds in datasets)

    aviso = ('<span class="mock">⚠ DADOS FABRICADOS (--mock) — só pra validar o formato.</span> '
             if modo == "mock" else "")

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>gpt-4o × mini · 4 datasets</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f2f2f0;color:#18181b;padding:24px 16px 60px}}
.container{{max-width:1280px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:4px}}
.sub-h{{color:#666;font-size:13px;margin-bottom:16px}}
.mock{{background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:6px;font-weight:600}}
.wrap{{overflow-x:auto;border:1px solid #e4e4e7;border-radius:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff;min-width:900px}}
th,td{{padding:8px 8px;border-bottom:1px solid #f0f0f0;text-align:center;white-space:nowrap}}
th{{background:#fafafa;color:#3f3f46}}
th.grp{{border-left:2px solid #e4e4e7;font-size:13px;padding-bottom:6px}}
th.m{{font-size:11px;color:#71717a;font-weight:500;padding:4px 8px}}
th.m.dh,td.delta{{border-right:1px solid #eee}}
th:first-child,td.crit{{text-align:left}}
td.crit{{font-weight:500;background:#fafafa;position:sticky;left:0}}
th:first-child{{position:sticky;left:0;z-index:2}}
.sub{{font-size:10px;color:#a1a1aa;font-weight:400;margin-top:1px}}
th .sub{{color:#71717a}}
td.na{{color:#c4c4c8}}
td.off{{background:#f6f6f5}}
td.nd{{color:#d4d4d8}}
td.delta{{font-weight:600}}
td.atual{{background:#eaf1fd;box-shadow:inset 0 -2px 0 #93b4e8}}
.hoje{{display:inline-block;margin-left:6px;font-size:9.5px;font-weight:600;padding:1px 5px;border-radius:5px;vertical-align:middle;letter-spacing:.2px}}
.hoje.h4o{{background:#e0e7ff;color:#3730a3}}
.hoje.hmini{{background:#e5e7eb;color:#475569}}
.sub2{{font-size:11px}}
tr.sec td{{background:#eef2f6;font-weight:600;text-align:left;color:#334155;font-size:12px;border-top:2px solid #e4e4e7}}
tr.resumo td{{background:#f8fafc;border-top:2px solid #e4e4e7}}
tr.resumo td.crit{{background:#f1f5f9}}
.leg{{margin-top:14px;font-size:12px;color:#71717a;line-height:1.5}}
.leg b{{color:#18181b}}
</style></head><body><div class="container">
<h1>gpt-4o × gpt-4o-mini — acerto por critério nos 4 datasets</h1>
<p class="sub-h">{aviso}<b>4o</b> = referência · <b>Δ</b> = mini − 4o (verde = mini igualou/superou → dá pra baixar; vermelho = regrediu) · acerto vs verdade humana<br>
<span class="hoje h4o">4o hoje</span> / <span class="hoje hmini">mini hoje</span> = <b>modelo que roda esse critério HOJE em produção</b> (a sub-coluna dele fica destacada em azul)</p>
<div class="wrap"><table>
<thead>
<tr><th rowspan="2">Critério</th>{grp_th}</tr>
<tr>{sub_th}</tr>
</thead>
<tbody>
{"".join(secoes)}
<tr class="resumo"><td class="crit">Itens 100% certos</td>{r100}</tr>
<tr class="resumo"><td class="crit">Custo do run</td>{rcusto}</tr>
</tbody></table></div>
<p class="leg"><b>Sub-coluna destacada (azul)</b> = o modelo que roda esse critério HOJE em produção (selo <span class="hoje h4o">4o hoje</span>/<span class="hoje hmini">mini hoje</span> no rótulo). Leia o Δ como "o que muda se eu trocar pro outro modelo".<br>
Célula vazia (fundo cinza) = <b>o critério não existe naquele pipeline</b> (regra Ville ≠ Sundek). "—" = dataset sem verdade humana.<br>
<b>Δ verde</b> = o mini igualou ou superou o 4o → candidato a rodar no mini ali. <b>Δ vermelho</b> = o mini piorou, mantém o 4o. Custo é só deste run (não do mês); Δ de custo verde = mini mais barato.<br>
Obs.: a marca Sundek roda no mini, com re-checagem pontual no 4o quando o título cita "sundek".</p>
</div></body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Comparativo 4o × mini nos 4 datasets.")
    ap.add_argument("--mock", action="store_true", help="gera HTML com dados fabricados (não gasta IA)")
    ap.add_argument("--limit", type=int, default=None, help="roda só os N primeiros itens por dataset (smoke test)")
    ap.add_argument("--workers", type=int, default=4, help="threads por modelo (default 4)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / "comparativo-datasets.html"

    if args.mock:
        datasets = _mock()
        html_path.write_text(_html(datasets, "mock"), encoding="utf-8")
        print(f"✓ HTML MOCK (só formato): {html_path}")
        print("  Abra pra validar o layout. Sem IA gasta. Depois rode sem --mock.")
        return

    if not TRUTH_PATH.exists():
        print(f"Falta a verdade em {TRUTH_PATH}. Rode antes: python -m src.tests.gabarito.gabarito_export")
        return
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))["respostas"]

    print(f"Modelos: {REF} (ref) × {CAND}\n")
    # 1) Pré-pass sem IA: monta os inputs pra sabermos o total antes de começar.
    datasets = [_plano_dataset(chave, rotulo, familia, truth, args.limit)
                for chave, rotulo, familia in DATASETS]
    n_shorts = sum(len(ds["inputs"]) for ds in datasets if ds["disponivel"])
    total = n_shorts * len(MODELOS)
    if not total:
        print("\nNenhum dataset com verdade humana pra rodar. Rode gabarito_export.")
        return
    print(f"\n=== {n_shorts} shorts × {len(MODELOS)} modelos = {total} análises · "
          f"{args.workers} workers ===")

    # 2) Roda alimentando o progresso GLOBAL (status + ETA a cada short).
    prog = _Prog(total)
    for ds in datasets:
        if ds["disponivel"]:
            _rodar_plano(ds, truth, args.workers, prog)
    print(f"\n✓ Todas as {total} análises concluídas em {_dur(time.time() - prog.t0)}.")

    comp = {"modelos": MODELOS, "datasets": [
        {k: v for k, v in ds.items() if k != "por_modelo"}
        | {"por_modelo": {m: {kk: vv for kk, vv in r.items() if kk != "itens"}
                          for m, r in ds.get("por_modelo", {}).items()}}
        for ds in datasets]}
    (OUT_DIR / "comparativo-datasets.json").write_text(
        json.dumps(comp, ensure_ascii=False, indent=1), encoding="utf-8")
    html_path.write_text(_html(datasets, "real"), encoding="utf-8")
    print(f"\n✓ HTML: {html_path}")
    print(f"✓ JSON: {OUT_DIR / 'comparativo-datasets.json'}")


if __name__ == "__main__":
    main()
