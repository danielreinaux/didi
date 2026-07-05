"""Comparativo de MODELOS no gabarito — acerto por dataset × critério + custo.

Roda o MESMO pipeline do gabarito (os agentes da Ville, via _processar do
gabarito_run) com vários modelos e mede o acerto por critério contra a verdade
humana, além do custo/tokens de cada modelo. Serve pra responder:
"em quais critérios dá pra usar um modelo mais barato sem perder precisão?".

⚠️ Fica numa pasta SEPARADA (src/tests/modeltest, saída em data/modeltest/) — NÃO mexe
no data/regressao/ do gabarito de regressão nem nas rodadas versionadas dele.

Como funciona:
  • "atual"  = roda com o config de produção (mini nos rápidos + gpt-4o nos finos).
               É a linha de comparação (baseline).
  • "<modelo>" = roda TUDO naquele modelo (troca config.IA em memória).
  • Cada agente é precificado pelo modelo que REALMENTE usou (por isso o baseline
    misto sai com custo correto).
  • Um monkeypatch tolera modelos que rejeitam temperature/response_format
    (ex.: alguns GPT-5.x) — reenvia a chamada sem o parâmetro.

Uso:
  # teste barato primeiro (só 6 itens, pra ver que roda):
  python -m src.tests.modeltest.run --limit 6

  # comparativo completo (dataset ville, set padrão de modelos):
  python -m src.tests.modeltest.run

  # escolher modelos e dataset:
  python -m src.tests.modeltest.run --dataset ville --models atual,gpt-4o-mini,gpt-4.1-nano
  python -m src.tests.modeltest.run --workers 6

Saída:
  data/modeltest/<dataset>/<modelo>.json   → respostas cruas da IA por item
  data/modeltest/comparativo-<dataset>.json
  data/modeltest/comparativo-<dataset>.html  ← abra este pro comparativo destrinchado
"""
import argparse
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import openai

from ...config import IA as CONFIG_IA
from ..gabarito import gabarito_run as gr
from ..gabarito.gabarito_diff import _norm, _graded, _item_100, CRITERIOS, LABELS

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA = ROOT / "data"
OUT_DIR = DATA / "modeltest"
TRUTH_PATH = DATA / "regressao" / "gabarito_respostas.json"
USD_BRL = 5.0

# Preços OpenAI (USD por 1M tokens) — jul/2026. Ajuste aqui se a OpenAI mudar.
# (Não modelamos cached input; em produção o prefixo estável pode sair mais barato.)
PRECOS = {
    "gpt-4o-mini":  {"in": 0.15, "out": 0.60},
    "gpt-4o":       {"in": 2.50, "out": 10.00},
    "gpt-4.1":      {"in": 2.00, "out": 8.00},
    "gpt-4.1-mini": {"in": 0.40, "out": 1.60},
    "gpt-4.1-nano": {"in": 0.10, "out": 0.40},
    "gpt-5.4":      {"in": 2.50, "out": 15.00},
    "gpt-5.4-mini": {"in": 0.75, "out": 4.50},
    "gpt-5.4-nano": {"in": 0.20, "out": 1.25},
}

# Set padrão: baseline atual (já usa gpt-4o nos finos) + candidatos do mais barato ao
# intermediário. O teto "gpt-4o" fica de fora pra baratear o teste (o "atual" já
# representa ele nos critérios finos) — adicione via --models se quiser o teto puro.
# Sobrescreva tudo com --models.
MODELOS_PADRAO = [
    "atual",         # config de produção (mini + gpt-4o nos finos) — referência
    "gpt-4o-mini",   # "tudo no mini" — o 1º teste que você pediu
    "gpt-4.1-nano",  # mais barato de todos
    "gpt-5.4-nano",  # cache barato + modelo novo
    "gpt-4.1-mini",  # degrau intermediário
    "gpt-5.4-mini",  # intermediário "esperto"
]

# Qual chave do config cada agente da Ville usa (pra precificar por-agente).
# marca/tartaruga/autenticidade/fecho = model_detalhes; cor/etiqueta/cordao = model.
AGENTE_CHAVE = {
    "marca": "model_detalhes", "tartaruga": "model_detalhes",
    "autenticidade": "model_detalhes", "fecho": "model_detalhes",
    "cor": "model", "etiqueta": "model", "cordao": "model",
}

# Acumulador de custo por modelo REAL usado (thread-safe), zerado a cada linha.
_custo_lock = threading.Lock()
_custo_por_modelo: dict = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0})


# ─────────────────────────────────────────────────────────────────────────────
# Resiliência de parâmetros: alguns modelos novos rejeitam temperature/json_object.
# ─────────────────────────────────────────────────────────────────────────────
def _instalar_patch_parametros() -> None:
    try:
        from openai.resources.chat.completions import Completions
    except Exception:
        return  # SDK diferente — segue sem patch (modelo incompatível falhará por item)
    orig = Completions.create

    def create_tolerante(self, *args, **kwargs):
        # Modelos novos (GPT-5.x) trocaram/limitaram parâmetros do chat.completions.
        # A cada erro 400 de PARÂMETRO, corrigimos UM e reenviamos (até 5x). Erro que
        # não seja de parâmetro (rede/cota/etc.) sobe na hora — sem loop à toa.
        for _ in range(5):
            try:
                return orig(self, *args, **kwargs)
            except Exception as e:
                msg = str(e).lower()
                # GPT-5.x: max_tokens → max_completion_tokens (com folga pro reasoning,
                # senão o orçamento pequeno dos agentes trunca a resposta e vem vazio).
                if "max_tokens" in msg and "max_tokens" in kwargs:
                    kwargs["max_completion_tokens"] = max(int(kwargs.pop("max_tokens")), 4000)
                    continue
                # Alguns só aceitam temperature default (1) → tira o 0.1.
                if "temperature" in msg and "temperature" in kwargs:
                    kwargs.pop("temperature")
                    continue
                # Último recurso: remove response_format se o modelo não suportar.
                if "response_format" in msg and "response_format" in kwargs:
                    kwargs.pop("response_format")
                    continue
                raise
        return orig(self, *args, **kwargs)

    Completions.create = create_tolerante


def _wrap_agentes() -> None:
    """Embrulha gr.FN pra capturar tokens POR agente (e o modelo que ele usou)."""
    originais = dict(gr.FN)

    def wrapper(agente: str, fn):
        def chamada(item):
            res = fn(item)
            if isinstance(res, dict):
                u = res.get("_usage", {}) or {}
                modelo = CONFIG_IA.get(AGENTE_CHAVE.get(agente, "model"))
                with _custo_lock:
                    d = _custo_por_modelo[modelo]
                    d["in"] += u.get("prompt_tokens", 0)
                    d["out"] += u.get("completion_tokens", 0)
                    d["calls"] += 1
            return res
        return chamada

    gr.FN = {a: wrapper(a, fn) for a, fn in originais.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Execução de um modelo
# ─────────────────────────────────────────────────────────────────────────────
def _custo_usd(por_modelo: dict) -> float:
    total = 0.0
    for modelo, v in por_modelo.items():
        p = PRECOS.get(modelo, {"in": 0.0, "out": 0.0})
        total += (v["in"] / 1e6) * p["in"] + (v["out"] / 1e6) * p["out"]
    return total


def _rodar_modelo(spec: str, inputs: list[dict], workers: int) -> dict:
    """Roda o pipeline inteiro num modelo. spec='atual' usa o config de produção."""
    global _custo_por_modelo
    with _custo_lock:
        _custo_por_modelo = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0})

    if spec != "atual":
        CONFIG_IA["model"] = spec
        CONFIG_IA["model_detalhes"] = spec

    resultados: dict = {}
    erros = 0
    rodar = set(gr.ORDEM)
    t0 = time.time()

    def processa(inp):
        try:
            out, _i, _o = gr._processar(inp, rodar, None)
            return inp["id"], out, None
        except Exception as e:
            return inp["id"], {c: None for c in CRITERIOS}, str(e)[:120]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(processa, inp) for inp in inputs]
        for i, fut in enumerate(as_completed(futs), 1):
            iid, out, err = fut.result()
            resultados[iid] = out
            if err:
                erros += 1
            print(f"  [{spec}] {i}/{len(inputs)}" + (f"  ⚠ {err}" if err else ""), flush=True)

    with _custo_lock:
        custo_modelo = {k: dict(v) for k, v in _custo_por_modelo.items()}
    return {
        "spec": spec,
        "itens": resultados,
        "erros": erros,
        # Se TODOS os itens falharam, o modelo está indisponível (sem acesso na conta,
        # id errado, etc.) — não é "0% de acerto", é "não rodou".
        "disponivel": erros < len(inputs),
        "custo_por_modelo": custo_modelo,
        "custo_usd": _custo_usd(custo_modelo),
        "tok_in": sum(v["in"] for v in custo_modelo.values()),
        "tok_out": sum(v["out"] for v in custo_modelo.values()),
        "calls": sum(v["calls"] for v in custo_modelo.values()),
        "duracao_s": round(time.time() - t0, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pontuação (mesma lógica do gabarito_aval)
# ─────────────────────────────────────────────────────────────────────────────
def _pontuar(resultados: dict, truth: dict, ids: list[str]) -> dict:
    por_criterio = {}
    for c in CRITERIOS:
        n = ok = 0
        for iid in ids:
            t = truth[iid]
            if not _graded(t, c):
                continue
            n += 1
            if _norm(resultados.get(iid, {}).get(c)) == _norm(t.get(c)):
                ok += 1
        por_criterio[c] = {"ok": ok, "n": n, "acc": (ok / n * 100) if n else None}

    avaliaveis = [i for i in ids if _item_100(resultados.get(i, {}), truth[i]) is not None]
    full = sum(1 for i in avaliaveis if _item_100(resultados.get(i, {}), truth[i]))
    return {
        "por_criterio": por_criterio,
        "itens_100": full,
        "itens_avaliaveis": len(avaliaveis),
        "pct_100": (full / len(avaliaveis) * 100) if avaliaveis else 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Relatórios
# ─────────────────────────────────────────────────────────────────────────────
def _cor_delta(d: float) -> str:
    if d >= 1:
        return "#15803d"   # melhorou
    if d <= -1:
        return "#b91c1c"   # regrediu
    return "#71717a"       # empatou


def _html(dataset: str, linhas: list[dict], n_itens: int) -> str:
    base = next((l for l in linhas if l["spec"] == "atual"), linhas[0])
    def acc(l, c):
        return l["score"]["por_criterio"][c]["acc"]

    # Cabeçalho de modelos
    ths = "".join(
        f'<th>{escape(l["spec"])}<div class="sub">'
        + ('⚠ indisponível' if not l["disponivel"] else f'${l["custo_usd"]:.3f} · R${l["custo_usd"]*USD_BRL:.2f}')
        + '</div></th>'
        for l in linhas
    )
    # Linhas por critério
    trs = []
    for c in CRITERIOS:
        cells = []
        a_base = acc(base, c) if base["disponivel"] else None
        for l in linhas:
            if not l["disponivel"]:
                cells.append('<td class="na">—</td>')
                continue
            a = acc(l, c)
            sc = l["score"]["por_criterio"][c]
            if a is None:
                cells.append('<td class="na">—</td>')
                continue
            delta = (a - a_base) if (a_base is not None) else 0
            dtxt = "" if l["spec"] == "atual" or a_base is None else f'<span style="color:{_cor_delta(delta)}"> {"+" if delta>=0 else ""}{delta:.0f}</span>'
            cells.append(f'<td><b>{a:.0f}%</b>{dtxt}<div class="sub">{sc["ok"]}/{sc["n"]}</div></td>')
        trs.append(f'<tr><td class="crit">{escape(LABELS.get(c, c))}</td>{"".join(cells)}</tr>')

    # Linhas-resumo
    r100 = "".join(
        ('<td class="na">—</td>' if not l["disponivel"]
         else f'<td><b>{l["score"]["pct_100"]:.0f}%</b><div class="sub">{l["score"]["itens_100"]}/{l["score"]["itens_avaliaveis"]}</div></td>')
        for l in linhas)
    rcusto = "".join(
        ('<td class="na">—</td>' if not l["disponivel"]
         else f'<td>${l["custo_usd"]:.3f}<div class="sub">R$ {l["custo_usd"]*USD_BRL:.2f}</div></td>')
        for l in linhas)
    rtok = "".join(f'<td class="sub">{l["tok_in"]:,} in / {l["tok_out"]:,} out<br>{l["calls"]} calls · {l["duracao_s"]}s{" · ⚠"+str(l["erros"])+" erros" if l["erros"] else ""}</td>' for l in linhas)

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comparativo de modelos · {escape(dataset)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f2f2f0;color:#18181b;padding:24px 16px 60px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:4px}}
.sub-h{{color:#666;font-size:13px;margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #e4e4e7;border-radius:10px;overflow:hidden}}
th,td{{padding:9px 10px;border-bottom:1px solid #f0f0f0;text-align:center}}
th{{background:#fafafa;font-size:12px;color:#3f3f46;border-bottom:2px solid #e4e4e7}}
th:first-child,td.crit{{text-align:left}}
td.crit{{font-weight:600;background:#fafafa}}
.sub{{font-size:10.5px;color:#a1a1aa;font-weight:400;margin-top:2px}}
th .sub{{color:#71717a}}
td.na{{color:#d4d4d8}}
tr.resumo td{{background:#f8fafc;border-top:2px solid #e4e4e7}}
tr.resumo td.crit{{background:#f1f5f9}}
.leg{{margin-top:14px;font-size:12px;color:#71717a}}
.leg b{{color:#18181b}}
</style></head><body><div class="container">
<h1>Comparativo de modelos — dataset <b>{escape(dataset)}</b></h1>
<p class="sub-h">{n_itens} itens com verdade humana · acerto por critério · Δ (colorido) = vs coluna <b>atual</b> · custo do run inteiro (não do mês)</p>
<table>
<thead><tr><th>Critério</th>{ths}</tr></thead>
<tbody>
{"".join(trs)}
<tr class="resumo"><td class="crit">Itens 100% certos</td>{r100}</tr>
<tr class="resumo"><td class="crit">Custo do run</td>{rcusto}</tr>
<tr class="resumo"><td class="crit">Tokens / chamadas</td>{rtok}</tr>
</tbody></table>
<p class="leg">Δ verde = o modelo <b>igualou ou superou</b> o atual naquele critério (dá pra baixar o modelo ali). Δ vermelho = regrediu. <b>ok/n</b> = acertos sobre itens avaliados. Custo é só deste teste (50 itens), não do mês.</p>
</div></body></html>"""


def _console(linhas: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("COMPARATIVO POR CRITÉRIO (acerto %)")
    print("=" * 78)
    specs = [l["spec"] for l in linhas]
    print(f"{'critério':<16}" + "".join(f"{s[:11]:>12}" for s in specs))
    print("-" * (16 + 12 * len(specs)))
    for c in CRITERIOS:
        cells = []
        for l in linhas:
            if not l["disponivel"]:
                cells.append(f"{'n/d':>11}")
                continue
            a = l["score"]["por_criterio"][c]["acc"]
            cells.append(f"{a:>10.0f}%" if a is not None else f"{'—':>11}")
        print(f"{LABELS.get(c, c):<16}" + "".join(f"{x:>12}" for x in cells))
    print("-" * (16 + 12 * len(specs)))
    print(f"{'itens 100%':<16}" + "".join(f"{l['score']['pct_100']:>11.0f}%" for l in linhas))
    print(f"{'custo USD':<16}" + "".join(f"{l['custo_usd']:>11.3f} " for l in linhas))
    print(f"{'custo R$':<16}" + "".join(f"{l['custo_usd']*USD_BRL:>11.2f} " for l in linhas))


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Comparativo de modelos no gabarito.")
    ap.add_argument("--dataset", default="ville", help="dataset do gabarito (default ville)")
    ap.add_argument("--models", default=None, help="lista separada por vírgula (default: set embutido)")
    ap.add_argument("--workers", type=int, default=6, help="threads por modelo (default 6)")
    ap.add_argument("--limit", type=int, default=None, help="roda só os N primeiros itens (teste barato)")
    args = ap.parse_args()

    if not TRUTH_PATH.exists():
        print(f"Falta a verdade em {TRUTH_PATH}. Rode antes: python -m src.tests.gabarito.gabarito_export")
        return
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))["respostas"]

    inputs = gr._montar_inputs(args.dataset)
    if args.limit:
        inputs = inputs[:args.limit]
    ids = [i["id"] for i in inputs if i["id"] in truth and isinstance(truth[i["id"]], dict) and truth[i["id"]]]
    if not ids:
        print(f"Nenhum item do dataset '{args.dataset}' tem verdade preenchida. "
              f"(Preencha o gabarito e rode gabarito_export.)")
        return
    print(f"Dataset '{args.dataset}': {len(inputs)} itens rodados, {len(ids)} com verdade humana.")

    modelos = [m.strip() for m in args.models.split(",")] if args.models else MODELOS_PADRAO
    print(f"Modelos: {', '.join(modelos)}\n")

    _instalar_patch_parametros()
    _wrap_agentes()
    orig_ia = dict(CONFIG_IA)

    (OUT_DIR / args.dataset).mkdir(parents=True, exist_ok=True)
    linhas = []
    try:
        for spec in modelos:
            print(f"→ rodando modelo: {spec}")
            r = _rodar_modelo(spec, inputs, args.workers)
            r["score"] = _pontuar(r["itens"], truth, ids)
            # respostas cruas por modelo (inspecionável)
            safe = spec.replace("/", "_")
            (OUT_DIR / args.dataset / f"{safe}.json").write_text(
                json.dumps(r["itens"], ensure_ascii=False, indent=1), encoding="utf-8")
            linhas.append(r)
            if not r["disponivel"]:
                print(f"   ⚠ {spec}: INDISPONÍVEL — todos os {r['erros']} itens falharam "
                      f"(sem acesso ao modelo na conta ou id errado). Tire-o do --models se quiser.")
            else:
                print(f"   ✓ {spec}: 100%={r['score']['pct_100']:.0f}% · ${r['custo_usd']:.3f} · {r['duracao_s']}s"
                      + (f" · ⚠ {r['erros']} erros" if r['erros'] else ""))
    finally:
        # restaura o config de produção sempre
        CONFIG_IA.update(orig_ia)

    # relatórios
    comp = {"dataset": args.dataset, "n_itens": len(ids),
            "linhas": [{k: v for k, v in l.items() if k != "itens"} for l in linhas]}
    (OUT_DIR / f"comparativo-{args.dataset}.json").write_text(
        json.dumps(comp, ensure_ascii=False, indent=1), encoding="utf-8")
    html_path = OUT_DIR / f"comparativo-{args.dataset}.html"
    html_path.write_text(_html(args.dataset, linhas, len(ids)), encoding="utf-8")

    _console(linhas)
    print(f"\n✓ HTML destrinchado: {html_path}")
    print(f"✓ JSON: {OUT_DIR / f'comparativo-{args.dataset}.json'}")
    print(f"✓ Respostas cruas por modelo: {OUT_DIR / args.dataset}/")


if __name__ == "__main__":
    main()
