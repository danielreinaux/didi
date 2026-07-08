"""Compara DUAS rodadas Sundek contra o gabarito — onde a IA evoluiu/regrediu.

Por critério: acerto da rodada A vs B + Δ (↑ melhorou / ↓ piorou), e as listas de
itens que FLIPARAM (acertou→errou = regressão; errou→acertou = melhoria) — pra ver
o efeito exato da mudança de prompt. Ignora `humano=n_a` (não se aplica), igual o
aval. SEM gastar IA (só compara rodadas já geradas).

Uso:
  python -m src.tests.gabarito.gabarito_run_sundek --label sundek-baseline
  # (edita prompts)
  python -m src.tests.gabarito.gabarito_run_sundek --so listra,elastico,cor,bolso
  python -m src.tests.gabarito.gabarito_diff_sundek --de sundek-baseline --para sundek-v1
"""
import sys
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .gabarito_diff import _norm, _carregar, REG, PUBLIC
from .gabarito_run import _arg, _carregar_rodada, _ultima_rodada
from .gabarito_aval_sundek import CRITERIOS, LABELS, _aplica, _item_100, DATASET


def _acertos(rod_itens: dict, truth: dict, ids: list) -> dict:
    """Por critério: {crit: {iid: True/False}} — só onde o humano avaliou (aplicável)."""
    out = {c: {} for c in CRITERIOS}
    for iid in ids:
        t = truth[iid]
        ia = rod_itens.get(iid, {})
        for c in CRITERIOS:
            if _aplica(t, c):
                out[c][iid] = _norm(ia.get(c)) == _norm(t.get(c))
    return out


def main() -> None:
    truth = _carregar(REG / "gabarito_respostas.json", "gabarito (gabarito_export)")["respostas"]
    meta = {str(x["id"]): x for x in _carregar(PUBLIC / "gabarito_sundek.json", "gabarito_sundek")["itens"]}

    de = _arg("--de", f"{DATASET}-baseline")
    para = _arg("--para") or _ultima_rodada(DATASET)
    if not para or para == de:
        print(f"Preciso de 2 rodadas diferentes. --de {de} --para <rodada>. "
              f"Rode gabarito_run_sundek pra gerar uma versão nova.")
        sys.exit(1)
    A = _carregar_rodada(de)
    B = _carregar_rodada(para)
    for lbl, r in ((de, A), (para, B)):
        if not r:
            print(f"Rodada '{lbl}' não existe.")
            sys.exit(1)

    RA, RB = A["itens"], B["itens"]
    ids = [i for i in RB if i in RA and i in truth and isinstance(truth[i], dict) and truth[i]]
    accA, accB = _acertos(RA, truth, ids), _acertos(RB, truth, ids)

    # ── Por critério: acc A vs B + Δ + flips ─────────────────────────
    linhas = []  # (crit, pctA, pctB, delta, n, regrediu[], melhorou[])
    for c in CRITERIOS:
        comuns = [i for i in ids if i in accA[c] and i in accB[c]]
        n = len(comuns)
        if not n:
            linhas.append((c, None, None, None, 0, [], []))
            continue
        pA = sum(accA[c][i] for i in comuns) / n * 100
        pB = sum(accB[c][i] for i in comuns) / n * 100
        regrediu = [i for i in comuns if accA[c][i] and not accB[c][i]]
        melhorou = [i for i in comuns if not accA[c][i] and accB[c][i]]
        linhas.append((c, pA, pB, pB - pA, n, regrediu, melhorou))

    fullA = _full(RA, truth, ids)
    fullB = _full(RB, truth, ids)

    # ── Console ──────────────────────────────────────────────────────
    print(f"\n=== Diff Sundek · '{de}' → '{para}' · {len(ids)} itens ===\n")
    print(f"{'ÁREA':<20}{'n':>4}{de[:10]:>12}{para[:10]:>12}{'Δ':>8}")
    print("-" * 56)
    for c, pA, pB, d, n, reg, mel in sorted(
        [l for l in linhas if l[1] is not None], key=lambda x: x[3]
    ):
        seta = "↑" if d > 0 else ("↓" if d < 0 else "=")
        print(f"{LABELS[c]:<20}{n:>4}{pA:>11.0f}%{pB:>11.0f}%{d:>+7.0f}% {seta}")
    print("-" * 56)
    dfull = fullB[0] - fullA[0]
    print(f"{'ITENS 100% CERTOS':<20}{'':>4}{fullA[0]:>10}/{fullA[1]}{fullB[0]:>8}/{fullB[1]}{dfull:>+7} it")

    print("\n--- Flips (id · o que mudou) ---")
    for c, pA, pB, d, n, reg, mel in linhas:
        if not reg and not mel:
            continue
        print(f"\n[{LABELS[c]}]  +{len(mel)} / -{len(reg)}")
        for i in mel:
            print(f"  ✓ {i}: {_norm(RA[i].get(c))} → {_norm(RB[i].get(c))}  (agora bate com {_norm(truth[i].get(c))})")
        for i in reg:
            print(f"  ✗ {i}: {_norm(RA[i].get(c))} → {_norm(RB[i].get(c))}  (verdade={_norm(truth[i].get(c))})")

    _html(de, para, linhas, fullA, fullB, len(ids), RA, RB, truth, meta)


def _full(rod_itens: dict, truth: dict, ids: list) -> tuple[int, int]:
    aval = [i for i in ids if _item_100(rod_itens.get(i, {}), truth[i]) is not None]
    full = sum(1 for i in aval if _item_100(rod_itens.get(i, {}), truth[i]))
    return full, len(aval)


def _html(de, para, linhas, fullA, fullB, n_itens, RA, RB, truth, meta) -> None:
    rows = []
    for c, pA, pB, d, n, reg, mel in sorted(
        [l for l in linhas if l[1] is not None], key=lambda x: x[3]
    ) + [l for l in linhas if l[1] is None]:
        if pA is None:
            rows.append(f'<tr><td>{LABELS[c]}</td><td>0</td><td>—</td><td>—</td><td>—</td></tr>')
            continue
        dc = "#00ff88" if d > 0 else ("#ff4d6d" if d < 0 else "#8a8a94")
        rows.append(
            f'<tr><td>{LABELS[c]}</td><td style="color:#8a8a94">{n}</td>'
            f'<td>{pA:.0f}%</td><td style="font-weight:600">{pB:.0f}%</td>'
            f'<td style="color:{dc};font-weight:600">{d:+.0f}%</td></tr>'
        )

    flips = []
    for c, pA, pB, d, n, reg, mel in linhas:
        if not reg and not mel:
            continue
        blk = ""
        for i in mel:
            tit = escape((meta.get(i, {}).get("titulo") or "")[:45])
            blk += (f'<div style="font-size:12px;color:#00ff88">✓ {i} <span style="color:#8a8a94">{tit}</span> — '
                    f'{escape(_norm(RA[i].get(c)))} → {escape(_norm(RB[i].get(c)))}</div>')
        for i in reg:
            tit = escape((meta.get(i, {}).get("titulo") or "")[:45])
            blk += (f'<div style="font-size:12px;color:#ff4d6d">✗ {i} <span style="color:#8a8a94">{tit}</span> — '
                    f'{escape(_norm(RA[i].get(c)))} → {escape(_norm(RB[i].get(c)))} '
                    f'<span style="color:#8a8a94">(verdade: {escape(_norm(truth[i].get(c)))})</span></div>')
        flips.append(f'<div style="margin:12px 0"><div style="font-weight:600;margin-bottom:4px">'
                     f'{LABELS[c]} <span style="color:#8a8a94;font-weight:400">+{len(mel)} / -{len(reg)}</span></div>{blk}</div>')

    dfull = fullB[0] - fullA[0]
    fcor = "#00ff88" if dfull > 0 else ("#ff4d6d" if dfull < 0 else "#8a8a94")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diff Sundek · {escape(de)} → {escape(para)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0e0e12;color:#f5f5f7;padding:24px 16px;max-width:900px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#b8b8c0;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:8px 10px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.07)}}
th{{color:#8a8a94;font-weight:500}} td:nth-child(n+2),th:nth-child(n+2){{text-align:right}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px 18px;margin-bottom:18px}}
</style></head><body>
<h1>Diff Sundek</h1>
<div class="sub"><b>{escape(de)}</b> → <b>{escape(para)}</b> · {n_itens} itens · Δ = ganho/perda de acerto por critério</div>
<div class="card">
  <table><tr><th>Área</th><th>n</th><th>{escape(de[:12])}</th><th>{escape(para[:12])}</th><th>Δ</th></tr>{''.join(rows)}</table>
  <div style="font-size:15px;margin-top:12px">Itens 100% certos:
    {fullA[0]}/{fullA[1]} → <b>{fullB[0]}/{fullB[1]}</b> <span style="color:{fcor};font-weight:600">({dfull:+d} itens)</span></div>
</div>
<div class="card"><div style="font-weight:600;margin-bottom:8px">Flips (o que mudou de status)</div>
  {''.join(flips) if flips else '<div style="color:#8a8a94;font-size:13px">Nenhum flip — os dois rodam igual.</div>'}
</div>
</body></html>"""
    out = REG / f"diff-{de}--{para}.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nHTML -> {out}")


if __name__ == "__main__":
    main()
