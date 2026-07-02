"""Avalia UMA rodada contra o gabarito: acerto POR ÁREA + nº de itens 100% certos.

Use pra tirar a métrica do estado atual (ex.: a primeira rodada baseline), sem
precisar comparar duas versões. Pra comparar duas versões, use gabarito_diff.

Uso:
  python -m src.gabarito.gabarito_export             # puxa a verdade do Redis
  python -m src.gabarito.gabarito_run --label baseline
  python -m src.gabarito.gabarito_aval --label baseline
"""
import sys
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .gabarito_diff import (
    _arg, _norm, _carregar, _graded, _item_100,
    CRITERIOS, LABELS, REG, PUBLIC,
)


def main() -> None:
    from .gabarito_run import _ultima_rodada
    # Auto: sem --label, avalia a ÚLTIMA rodada do dataset (default ville).
    label = _arg("--label")
    if not label:
        dataset_arg = _arg("--dataset", "ville")
        label = _ultima_rodada(dataset_arg)
        if not label:
            print(f"Sem rodadas pro dataset '{dataset_arg}'. Rode gabarito_run primeiro.")
            sys.exit(1)

    truth = _carregar(REG / "gabarito_respostas.json", "gabarito (rode gabarito_export)")["respostas"]
    rod = _carregar(REG / f"rodada-{label}.json", f"rodada {label}")
    R = rod["itens"]
    dataset = rod.get("dataset", "ville")  # rodadas antigas = ville
    meta = {str(x["id"]): x for x in _carregar(PUBLIC / f"gabarito_{dataset}.json", f"gabarito_{dataset}")["itens"]}

    # Escopa aos itens desta rodada que têm gabarito preenchido.
    ids = [i for i in R if i in truth and isinstance(truth[i], dict) and truth[i]]
    if not ids:
        print("Gabarito vazio pra esta marca — ninguém preencheu. Nada a avaliar.")
        sys.exit(0)

    # ── Por área ─────────────────────────────────────────────────────
    areas = []  # (crit, acc, ok, n, erros[])
    for c in CRITERIOS:
        n = ok = 0
        erros = []
        for iid in ids:
            t = truth[iid]
            if not _graded(t, c):
                continue
            n += 1
            if _norm(R.get(iid, {}).get(c)) == _norm(t.get(c)):
                ok += 1
            else:
                erros.append(iid)
        acc = (ok / n * 100) if n else None
        areas.append((c, acc, ok, n, erros))

    # ── Global (itens 100% certos, com regra do portão) ──────────────
    avaliaveis = [i for i in ids if _item_100(R.get(i, {}), truth[i]) is not None]
    full = sum(1 for i in avaliaveis if _item_100(R.get(i, {}), truth[i]))
    pct_full = (full / len(avaliaveis) * 100) if avaliaveis else 0

    # ── Console ──────────────────────────────────────────────────────
    print(f"\n=== Desempenho da IA · dataset '{dataset}' · rodada '{label}' · {len(ids)} itens com gabarito ===\n")
    print(f"{'ÁREA':<18}{'acerto':>9}{'n':>5}")
    print("-" * 34)
    # ordena da pior pra melhor área (foco no que precisa melhorar)
    com_dados = [a for a in areas if a[1] is not None]
    sem_dados = [a for a in areas if a[1] is None]
    for c, acc, ok, n, _ in sorted(com_dados, key=lambda x: x[1]):
        print(f"{LABELS[c]:<18}{acc:>7.0f}% {n:>4}   ({ok}/{n})")
    for c, acc, ok, n, _ in sem_dados:
        print(f"{LABELS[c]:<18}{'—':>8} {0:>4}")
    print("-" * 34)
    print(f"{'ITENS 100% CERTOS':<18}{pct_full:>7.0f}%   {full}/{len(avaliaveis)}")

    # erros por área (pra você ir olhar)
    print("\n--- Onde a IA errou (id · IA → deveria ser | verdade) ---")
    for c, acc, ok, n, erros in areas:
        if not erros:
            continue
        print(f"\n[{LABELS[c]}]  ({len(erros)} erro(s))")
        for iid in erros:
            print(f"  {iid}: IA={_norm(R.get(iid,{}).get(c))}  ≠  verdade={_norm(truth[iid].get(c))}")

    _html(label, dataset, len(ids), areas, full, len(avaliaveis), pct_full, R, truth, meta)


def _html(label, dataset, n_itens, areas, full, n_aval, pct_full, R, truth, meta) -> None:
    linhas = []
    for c, acc, ok, n, erros in sorted(
        [a for a in areas if a[1] is not None], key=lambda x: x[1]
    ) + [a for a in areas if a[1] is None]:
        if acc is None:
            linhas.append(f'<tr><td>{LABELS[c]}</td><td>—</td><td>0</td></tr>')
            continue
        cor = "#00ff88" if acc >= 90 else ("#ffaa00" if acc >= 70 else "#ff4d6d")
        linhas.append(
            f'<tr><td>{LABELS[c]}</td>'
            f'<td style="color:{cor};font-weight:600">{acc:.0f}%</td>'
            f'<td style="color:#8a8a94">{ok}/{n}</td></tr>'
        )

    erros_html = []
    for c, acc, ok, n, erros in areas:
        if not erros:
            continue
        itens = ""
        for iid in erros:
            titulo = escape((meta.get(iid, {}).get("titulo") or "")[:55])
            url = escape(meta.get(iid, {}).get("url") or "#")
            itens += (f'<div style="font-size:12px;margin:2px 0">'
                      f'<a href="{url}" target="_blank" style="color:#00d9ff;text-decoration:none">{iid}</a> '
                      f'<span style="color:#8a8a94">{titulo}</span> — '
                      f'<b style="color:#ff4d6d">IA: {escape(_norm(R.get(iid,{}).get(c)))}</b> '
                      f'<span style="color:#8a8a94">| verdade: {escape(_norm(truth[iid].get(c)))}</span></div>')
        erros_html.append(f'<div style="margin:12px 0"><div style="font-weight:600;margin-bottom:4px">'
                          f'{LABELS[c]} <span style="color:#8a8a94;font-weight:400">({len(erros)} erro(s))</span></div>{itens}</div>')

    gcor = "#00ff88" if pct_full >= 70 else ("#ffaa00" if pct_full >= 40 else "#ff4d6d")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Desempenho IA · {escape(label)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0e0e12;color:#f5f5f7;padding:24px 16px;max-width:860px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#b8b8c0;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:8px 10px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.07)}}
th{{color:#8a8a94;font-weight:500}} td:nth-child(n+2),th:nth-child(n+2){{text-align:right}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px 18px;margin-bottom:18px}}
</style></head><body>
<h1>Desempenho da IA · {escape(dataset)}</h1>
<div class="sub">rodada <b>{escape(label)}</b> · {n_itens} itens com gabarito · acerto contra a verdade humana (áreas da pior pra melhor)</div>
<div class="card">
  <table><tr><th>Área</th><th>acerto</th><th>n</th></tr>{''.join(linhas)}</table>
  <div style="font-size:15px;margin-top:12px">Itens 100% certos:
    <b style="color:{gcor}">{full}/{n_aval}</b> <span style="color:#8a8a94">({pct_full:.0f}%)</span></div>
</div>
<div class="card"><div style="font-weight:600;margin-bottom:8px">Onde a IA errou</div>
  {''.join(erros_html) if erros_html else '<div style="color:#8a8a94;font-size:13px">Sem erros — 100% em tudo. 🎉</div>'}
</div>
</body></html>"""
    out = REG / f"aval-{label}.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nHTML -> {out}")


if __name__ == "__main__":
    main()
