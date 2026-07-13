"""Avalia a IA da Sundek contra o gabarito — SEM gastar IA (só compara).

Métrica: acerto POR CRITÉRIO (14 critérios da Sundek) + nº de itens 100% certos,
com a regra do portão (se a verdade diz que NÃO é Sundek / NÃO é short, basta a
IA acertar o portão). Gera HTML com a lista de erros por área.

De onde vem a resposta da IA:
  --label <rodada>  → lê a rodada gerada pelo gabarito_run_sundek (SEM short-circuit
                      → sem os `n_a` que quebram a métrica). É o modo correto.
  (sem --label)     → usa a ÚLTIMA rodada sundek; se não houver nenhuma, cai no
                      snapshot de PRODUÇÃO salvo em gabarito_sundek.json (com os
                      n_a do early-exit — só serve de "onde estávamos").

Uso:
  python -m src.tests.gabarito.gabarito_export              # re-puxa a verdade do Redis
  python -m src.tests.gabarito.gabarito_run_sundek --label sundek-baseline
  python -m src.tests.gabarito.gabarito_aval_sundek --label sundek-baseline
"""
import sys
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Reusa os helpers puros do harness Ville (normalização, carga, "avaliado?").
from .gabarito_diff import _norm, _graded, _carregar, REG, PUBLIC
from .gabarito_run import _arg, _carregar_rodada, _ultima_rodada

# ── Os 14 critérios da Sundek (espelham o gabarito_sundek.py / a página) ──
CRITERIOS = [
    "e_sundek", "e_short", "tipo", "aparencia", "tecido_brilhoso", "listra",
    "bicolor", "cor_tier", "tem_elastico", "fechamento", "bolso_traseiro",
    "bolso_nome", "bolso_frontal", "etiqueta",
]
LABELS = {
    "e_sundek": "É Sundek?", "e_short": "É short?", "tipo": "Tipo",
    "aparencia": "Aparência", "tecido_brilhoso": "Tecido brilhoso?",
    "listra": "Listra lateral", "bicolor": "Bicolor?", "cor_tier": "Cor (tier)",
    "tem_elastico": "Tem elástico?", "fechamento": "Fechamento",
    "bolso_traseiro": "Bolso traseiro?", "bolso_nome": 'Patch "SUNDEK"?',
    "bolso_frontal": "Bolso frontal/cargo?", "etiqueta": "Etiqueta (hang tag)",
}
# Portão: se a verdade nega um destes, o item deveria ser descartado de cara.
GATE_CRITS = ("e_sundek", "e_short")
DATASET = "sundek"
# Rótulo amigável por dataset (só cosmético: títulos/cabeçalhos).
ROTULOS = {"sundek": "Sundek", "compraveis_sundek": "Sundek compráveis"}


def _aplica(truth_item: dict, crit: str) -> bool:
    """O humano avaliou o critério com um valor APLICÁVEL? (não em branco e não
    'n_a'). Se ele marcou 'n_a' (não se aplica — ex.: cor de um item bicolor que
    ele já descartou), NÃO pontuamos: a IA dar um valor ali não é erro de prompt."""
    return _graded(truth_item, crit) and _norm(truth_item.get(crit)) != "n_a"


def _item_100(ia_item: dict, truth_item: dict):
    """Item 100% certo? None se o humano não avaliou nada. (Regra do portão.)"""
    graded = [c for c in CRITERIOS if _aplica(truth_item, c)]
    if not graded:
        return None
    excluir_no_gate = truth_item.get("e_sundek") == "nao" or truth_item.get("e_short") == "nao"
    if excluir_no_gate:
        alvos = [c for c in GATE_CRITS if truth_item.get(c) == "nao"]
    else:
        alvos = graded
    return all(_norm(ia_item.get(c)) == _norm(truth_item.get(c)) for c in alvos)


def main() -> None:
    # `--dataset` escolhe o conjunto congelado (sundek base ou compraveis_sundek).
    # Default = sundek (a constante DATASET), pra não quebrar quem chama sem o flag.
    dataset = _arg("--dataset", DATASET)
    truth = _carregar(REG / "gabarito_respostas.json",
                      "gabarito (rode gabarito_export)")["respostas"]
    base = _carregar(PUBLIC / f"gabarito_{dataset}.json", f"gabarito_{dataset}")["itens"]
    meta = {str(x["id"]): x for x in base}  # titulo/url pros links

    # De onde vem a resposta da IA (ver docstring): rodada do runner (correto) ou
    # snapshot de produção (fallback, com os n_a do early-exit).
    label = _arg("--label") or _ultima_rodada(dataset)
    if label:
        rod = _carregar_rodada(label)
        if not rod:
            print(f"Rodada '{label}' não existe. Rode: "
                  f"python -m src.tests.gabarito.gabarito_run_sundek --dataset {dataset} --label {label}")
            sys.exit(1)
        ia = {str(k): (v or {}) for k, v in rod["itens"].items()}
        fonte = f"rodada '{label}'"
    else:
        ia = {str(x["id"]): (x.get("ia") or {}) for x in base}
        fonte = f"PRODUÇÃO (gabarito_{dataset}.json — com n_a do early-exit)"
    print(f"Fonte da IA: {fonte}\n")

    # Escopa aos itens da base Sundek que têm gabarito preenchido.
    ids = [i for i in ia if i in truth and isinstance(truth[i], dict) and truth[i]]
    if not ids:
        print("Gabarito Sundek vazio — ninguém preencheu (ou o export está velho). "
              "Rode: python -m src.tests.gabarito.gabarito_export")
        sys.exit(0)

    # ── Acerto por área ──────────────────────────────────────────────
    areas = []  # (crit, acc, ok, n, erros[])
    for c in CRITERIOS:
        n = ok = 0
        erros = []
        for iid in ids:
            t = truth[iid]
            if not _aplica(t, c):
                continue
            n += 1
            if _norm(ia[iid].get(c)) == _norm(t.get(c)):
                ok += 1
            else:
                erros.append(iid)
        acc = (ok / n * 100) if n else None
        areas.append((c, acc, ok, n, erros))

    # ── Global (itens 100% certos, com portão) ───────────────────────
    avaliaveis = [i for i in ids if _item_100(ia[i], truth[i]) is not None]
    full = sum(1 for i in avaliaveis if _item_100(ia[i], truth[i]))
    pct_full = (full / len(avaliaveis) * 100) if avaliaveis else 0

    # ── Console ──────────────────────────────────────────────────────
    rotulo = ROTULOS.get(dataset, dataset)
    print(f"\n=== Desempenho da IA · {rotulo} · {len(ids)} itens com gabarito ===\n")
    print(f"{'ÁREA':<20}{'acerto':>9}{'n':>5}")
    print("-" * 36)
    com = [a for a in areas if a[1] is not None]
    sem = [a for a in areas if a[1] is None]
    for c, acc, ok, n, _ in sorted(com, key=lambda x: x[1]):
        print(f"{LABELS[c]:<20}{acc:>7.0f}% {n:>4}   ({ok}/{n})")
    for c, acc, ok, n, _ in sem:
        print(f"{LABELS[c]:<20}{'—':>8} {0:>4}")
    print("-" * 36)
    print(f"{'ITENS 100% CERTOS':<20}{pct_full:>7.0f}%   {full}/{len(avaliaveis)}")

    print("\n--- Onde a IA errou (id · IA ≠ verdade) ---")
    for c, acc, ok, n, erros in areas:
        if not erros:
            continue
        print(f"\n[{LABELS[c]}]  ({len(erros)} erro(s))")
        for iid in erros:
            print(f"  {iid}: IA={_norm(ia[iid].get(c))}  ≠  verdade={_norm(truth[iid].get(c))}")

    _html(label, fonte, len(ids), areas, full, len(avaliaveis), pct_full, ia, truth, meta, rotulo)


def _html(label, fonte, n_itens, areas, full, n_aval, pct_full, ia, truth, meta, rotulo="Sundek") -> None:
    linhas = []
    ordenadas = sorted([a for a in areas if a[1] is not None], key=lambda x: x[1]) \
        + [a for a in areas if a[1] is None]
    for c, acc, ok, n, erros in ordenadas:
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
                      f'<b style="color:#ff4d6d">IA: {escape(_norm(ia.get(iid,{}).get(c)))}</b> '
                      f'<span style="color:#8a8a94">| verdade: {escape(_norm(truth[iid].get(c)))}</span></div>')
        erros_html.append(f'<div style="margin:12px 0"><div style="font-weight:600;margin-bottom:4px">'
                          f'{LABELS[c]} <span style="color:#8a8a94;font-weight:400">({len(erros)} erro(s))</span></div>{itens}</div>')

    gcor = "#00ff88" if pct_full >= 70 else ("#ffaa00" if pct_full >= 40 else "#ff4d6d")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Desempenho IA · {escape(rotulo)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0e0e12;color:#f5f5f7;padding:24px 16px;max-width:860px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#b8b8c0;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;padding:8px 10px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.07)}}
th{{color:#8a8a94;font-weight:500}} td:nth-child(n+2),th:nth-child(n+2){{text-align:right}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px 18px;margin-bottom:18px}}
</style></head><body>
<h1>Desempenho da IA · {escape(rotulo)}</h1>
<div class="sub">{escape(fonte)} · {n_itens} itens com gabarito · acerto contra a verdade humana (áreas da pior pra melhor)</div>
<div class="card">
  <table><tr><th>Área</th><th>acerto</th><th>n</th></tr>{''.join(linhas)}</table>
  <div style="font-size:15px;margin-top:12px">Itens 100% certos:
    <b style="color:{gcor}">{full}/{n_aval}</b> <span style="color:#8a8a94">({pct_full:.0f}%)</span></div>
</div>
<div class="card"><div style="font-weight:600;margin-bottom:8px">Onde a IA errou</div>
  {''.join(erros_html) if erros_html else '<div style="color:#8a8a94;font-size:13px">Sem erros — 100% em tudo. 🎉</div>'}
</div>
</body></html>"""
    out = REG / f"aval-{label or 'sundek-producao'}.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nHTML -> {out}")


if __name__ == "__main__":
    main()
