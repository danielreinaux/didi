"""Comparativo de EVOLUÇÃO dos prompts Sundek CRUZANDO os 2 datasets num HTML só.

Diferente do gabarito_diff_sundek (um dataset por vez), aqui as COLUNAS são os
datasets (Sundek base e Sundek compráveis) e cada um vira 3 sub-colunas:
  antes | depois | Δ (depois − antes).
Linhas = os 14 critérios Sundek. É a "evolução do padrão de hoje": mede o efeito
de um refino de prompt nos DOIS datasets de uma vez, lado a lado.

Δ verde = o refino MELHOROU o acerto naquele critério+dataset; Δ vermelho = regrediu.
SEM gastar IA — só compara rodadas já geradas pelo gabarito_run_sundek.

Fluxo:
  # antes (estado atual do repo) — roda os 2:
  python -m src.tests.gabarito.gabarito_run_sundek --dataset sundek            --label sundek-pre --all
  python -m src.tests.gabarito.gabarito_run_sundek --dataset compraveis_sundek --label compraveis_sundek-pre --all
  # (edita prompts)
  # depois (auto-detecta o que mudou vs -pre):
  python -m src.tests.gabarito.gabarito_run_sundek --dataset sundek            --label sundek-pos --base sundek-pre
  python -m src.tests.gabarito.gabarito_run_sundek --dataset compraveis_sundek --label compraveis_sundek-pos --base compraveis_sundek-pre
  # comparativo cruzado:
  python -m src.tests.gabarito.gabarito_evolucao_sundek --pre pre --pos pos --refinados listra,cor_tier,fechamento

Saída: data/regressao/evolucao-sundek.html (matriz) + eco no console.
"""
import sys
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .gabarito_diff import _norm, _carregar, REG, PUBLIC
from .gabarito_run import _arg, _carregar_rodada
from .gabarito_aval_sundek import CRITERIOS, LABELS, _aplica, _item_100, ROTULOS

# Os 2 datasets Sundek, na ordem das colunas.
DATASETS = [("sundek", "Sundek"), ("compraveis_sundek", "Sundek compráveis")]


def _pontuar(rod_itens: dict, truth: dict, ids: list) -> tuple[dict, tuple[int, int]]:
    """Por critério: acerto vs verdade (só onde o humano avaliou/aplicável) +
    (itens 100% certos, itens avaliáveis)."""
    por = {}
    for c in CRITERIOS:
        n = ok = 0
        for iid in ids:
            t = truth[iid]
            if not _aplica(t, c):
                continue
            n += 1
            if _norm(rod_itens.get(iid, {}).get(c)) == _norm(t.get(c)):
                ok += 1
        por[c] = {"ok": ok, "n": n, "acc": (ok / n * 100) if n else None}
    aval = [i for i in ids if _item_100(rod_itens.get(i, {}), truth[i]) is not None]
    full = sum(1 for i in aval if _item_100(rod_itens.get(i, {}), truth[i]))
    return por, (full, len(aval))


def _dados_dataset(chave: str, rotulo: str, pre: str, pos: str, truth: dict) -> dict:
    """Carrega as rodadas -pre e -pos do dataset e pontua as duas contra a verdade."""
    lbl_pre, lbl_pos = f"{chave}-{pre}", f"{chave}-{pos}"
    A, B = _carregar_rodada(lbl_pre), _carregar_rodada(lbl_pos)
    if not A:
        print(f"⚠ Rodada '{lbl_pre}' não existe — pule ou rode o baseline do {chave}.")
        return {"chave": chave, "rotulo": rotulo, "ok": False}
    if not B:
        print(f"⚠ Rodada '{lbl_pos}' não existe — rode o refino do {chave}.")
        return {"chave": chave, "rotulo": rotulo, "ok": False}
    RA, RB = A["itens"], B["itens"]
    # Só itens presentes nas 2 rodadas E com verdade humana preenchida.
    ids = [i for i in RB if i in RA and i in truth and isinstance(truth[i], dict) and truth[i]]
    pA, fullA = _pontuar(RA, truth, ids)
    pB, fullB = _pontuar(RB, truth, ids)
    por = {}
    for c in CRITERIOS:
        a, b = pA[c]["acc"], pB[c]["acc"]
        por[c] = {"pre": pA[c], "pos": pB[c],
                  "delta": (b - a) if (a is not None and b is not None) else None}
    return {"chave": chave, "rotulo": rotulo, "ok": True, "n_itens": len(ids),
            "por": por, "full_pre": fullA, "full_pos": fullB,
            "lbl_pre": lbl_pre, "lbl_pos": lbl_pos}


# ─────────────────────────────────────────────────────────────────────────────
# Console
# ─────────────────────────────────────────────────────────────────────────────
def _console(datasets: list[dict], refinados: set) -> None:
    for ds in datasets:
        if not ds.get("ok"):
            continue
        print(f"\n=== {ds['rotulo']} · {ds['n_itens']} itens · "
              f"'{ds['lbl_pre']}' → '{ds['lbl_pos']}' ===")
        print(f"{'ÁREA':<22}{'antes':>8}{'depois':>9}{'Δ':>8}")
        print("-" * 47)
        linhas = [(c, d) for c, d in ds["por"].items() if d["pre"]["acc"] is not None]
        for c, d in sorted(linhas, key=lambda x: (x[1]["delta"] or 0)):
            seta = "↑" if (d["delta"] or 0) > 0 else ("↓" if (d["delta"] or 0) < 0 else "=")
            selo = " *" if c in refinados else ""
            print(f"{LABELS[c]+selo:<22}{d['pre']['acc']:>7.0f}%{d['pos']['acc']:>8.0f}%"
                  f"{(d['delta'] or 0):>+7.0f}% {seta}")
        fa, fb = ds["full_pre"], ds["full_pos"]
        print("-" * 47)
        print(f"{'ITENS 100% CERTOS':<22}{fa[0]:>4}/{fa[1]:<3}{fb[0]:>5}/{fb[1]:<3}"
              f"{(fb[0]-fa[0]):>+6} it")
    print("\n(* = critério cujo prompt foi refinado nesta rodada)")


# ─────────────────────────────────────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────────────────────────────────────
def _cor_delta(d) -> str:
    if d is None:
        return "#a1a1aa"
    if d >= 1:
        return "#15803d"   # melhorou
    if d <= -1:
        return "#b91c1c"   # regrediu
    return "#71717a"       # empate


def _cel_acc(sc) -> str:
    if sc is None or sc.get("acc") is None:
        return '<td class="na">—</td>'
    return f'<td><b>{sc["acc"]:.0f}%</b><div class="sub">{sc["ok"]}/{sc["n"]}</div></td>'


def _celulas(ds: dict, c: str) -> str:
    """3 <td> (antes | depois | Δ) do critério c na coluna deste dataset."""
    if not ds.get("ok"):
        return '<td class="nd">—</td><td class="nd">—</td><td class="nd">—</td>'
    d = ds["por"][c]
    a, b = d["pre"], d["pos"]
    if a["acc"] is None and b["acc"] is None:
        return '<td class="na">—</td><td class="na">—</td><td class="na">—</td>'
    dl = d["delta"]
    dtxt = "—" if dl is None else f'{"+" if dl >= 0 else ""}{dl:.0f}'
    return (_cel_acc(a) + _cel_acc(b)
            + f'<td class="delta" style="color:{_cor_delta(dl)}"><b>{dtxt}</b></td>')


def _cel_resumo(ds: dict) -> str:
    if not ds.get("ok"):
        return '<td class="nd">—</td><td class="nd">—</td><td class="nd">—</td>'
    fa, fb = ds["full_pre"], ds["full_pos"]
    pa = (fa[0] / fa[1] * 100) if fa[1] else 0
    pb = (fb[0] / fb[1] * 100) if fb[1] else 0
    d = pb - pa
    return (f'<td><b>{pa:.0f}%</b><div class="sub">{fa[0]}/{fa[1]}</div></td>'
            f'<td><b>{pb:.0f}%</b><div class="sub">{fb[0]}/{fb[1]}</div></td>'
            f'<td class="delta" style="color:{_cor_delta(d)}"><b>{"+" if d>=0 else ""}{d:.0f}</b></td>')


def _html(datasets: list[dict], refinados: set, pre: str, pos: str) -> str:
    grp_th = ""
    for ds in datasets:
        sub = (f'{ds["n_itens"]} itens' if ds.get("ok") else "sem rodada")
        grp_th += f'<th colspan="3" class="grp">{escape(ds["rotulo"])}<div class="sub">{sub}</div></th>'
    sub_th = "".join('<th class="m">antes</th><th class="m">depois</th><th class="m dh">Δ</th>'
                     for _ in datasets)

    linhas = []
    for c in CRITERIOS:
        selo = ('<span class="ref">refinado</span>' if c in refinados else '')
        cells = "".join(_celulas(ds, c) for ds in datasets)
        cls = ' class="reflinha"' if c in refinados else ''
        linhas.append(f'<tr{cls}><td class="crit">{escape(LABELS[c])}{selo}</td>{cells}</tr>')
    resumo = "".join(_cel_resumo(ds) for ds in datasets)

    # Saldo por dataset (quantos critérios subiram/desceram) pro cabeçalho.
    resumos_txt = []
    for ds in datasets:
        if not ds.get("ok"):
            continue
        subiu = sum(1 for c in CRITERIOS if (ds["por"][c]["delta"] or 0) >= 1)
        desceu = sum(1 for c in CRITERIOS if (ds["por"][c]["delta"] or 0) <= -1)
        resumos_txt.append(f'<b>{escape(ds["rotulo"])}</b>: {subiu} ↑ / {desceu} ↓')
    resumo_h = " · ".join(resumos_txt)

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evolução dos prompts Sundek · antes × depois</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f2f2f0;color:#18181b;padding:24px 16px 60px}}
.container{{max-width:1120px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:4px}}
.sub-h{{color:#666;font-size:13px;margin-bottom:16px;line-height:1.5}}
.wrap{{overflow-x:auto;border:1px solid #e4e4e7;border-radius:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff;min-width:720px}}
th,td{{padding:8px 8px;border-bottom:1px solid #f0f0f0;text-align:center;white-space:nowrap}}
th{{background:#fafafa;color:#3f3f46}}
th.grp{{border-left:2px solid #e4e4e7;font-size:14px;padding-bottom:6px}}
th.m{{font-size:11px;color:#71717a;font-weight:500;padding:4px 8px}}
th.m.dh,td.delta{{border-right:1px solid #eee}}
th:first-child,td.crit{{text-align:left}}
td.crit{{font-weight:500;background:#fafafa;position:sticky;left:0}}
th:first-child{{position:sticky;left:0;z-index:2}}
.sub{{font-size:10px;color:#a1a1aa;font-weight:400;margin-top:1px}}
th .sub{{color:#71717a}}
td.na{{color:#c4c4c8}} td.nd{{color:#d4d4d8}}
td.delta{{font-weight:600}}
tr.reflinha td{{background:#fffdf3}}
tr.reflinha td.crit{{background:#fdf6e3}}
.ref{{display:inline-block;margin-left:6px;font-size:9.5px;font-weight:600;padding:1px 6px;border-radius:5px;background:#fde68a;color:#92400e;vertical-align:middle}}
tr.resumo td{{background:#f8fafc;border-top:2px solid #e4e4e7;font-size:13px}}
tr.resumo td.crit{{background:#f1f5f9}}
.leg{{margin-top:14px;font-size:12px;color:#71717a;line-height:1.6}}
.leg b{{color:#18181b}}
</style></head><body><div class="container">
<h1>Evolução dos prompts Sundek — antes × depois nos 2 datasets</h1>
<p class="sub-h"><b>antes</b> = prompts no estado do repo (rótulo <code>-{escape(pre)}</code>) · <b>depois</b> = após o refino (<code>-{escape(pos)}</code>) · <b>Δ</b> = depois − antes (verde = melhorou, vermelho = regrediu) · acerto vs verdade humana.<br>
Saldo de critérios: {resumo_h}</p>
<div class="wrap"><table>
<thead>
<tr><th rowspan="2">Critério</th>{grp_th}</tr>
<tr>{sub_th}</tr>
</thead>
<tbody>
{"".join(linhas)}
<tr class="resumo"><td class="crit">Itens 100% certos</td>{resumo}</tr>
</tbody></table></div>
<p class="leg"><b>Linhas destacadas (amarelo)</b> = critérios cujo prompt foi refinado nesta rodada (selo <span class="ref">refinado</span>). Os demais devem ficar estáveis — se um deles mexer muito, é ruído a investigar.<br>
"—" numa célula = critério sem itens avaliáveis naquele dataset (ninguém preencheu / não se aplica). O mesmo prompt roda nos 2 datasets, então um refino aparece nas 2 colunas.</p>
</div></body></html>"""


def main() -> None:
    pre = _arg("--pre", "pre")
    pos = _arg("--pos", "pos")
    ref = _arg("--refinados", "")
    refinados = {x.strip() for x in ref.split(",") if x.strip()}
    invalidos = refinados - set(CRITERIOS)
    if invalidos:
        print(f"⚠ Critérios --refinados desconhecidos (ignorados): {invalidos}")
        refinados &= set(CRITERIOS)

    truth = _carregar(REG / "gabarito_respostas.json",
                      "gabarito (rode gabarito_export)")["respostas"]
    datasets = [_dados_dataset(ch, rot, pre, pos, truth) for ch, rot in DATASETS]

    _console(datasets, refinados)

    out = REG / "evolucao-sundek.html"
    out.write_text(_html(datasets, refinados, pre, pos), encoding="utf-8")
    print(f"\nHTML -> {out}")


if __name__ == "__main__":
    main()
