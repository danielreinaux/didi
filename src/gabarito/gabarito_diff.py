"""Compara duas RODADAS contra o gabarito e mostra onde a IA evoluiu/regrediu.

Por ÁREA (critério): % de acerto na rodada A vs B, com o Δ (↑ melhorou / ↓ piorou).
Geral: nº de itens 100% certos. E as listas de itens que FLIPARAM em cada área
(acertou→errou = regressão; errou→acertou = melhoria) — pra você ver exatamente
o efeito da mudança de prompt.

Uso:
  python -m src.gabarito.gabarito_diff --de baseline --para v2

Pré-requisitos:
  - python -m src.gabarito.gabarito_export        (puxa o gabarito do Redis)
  - python -m src.gabarito.gabarito_run --label baseline
  - (mexe nos prompts)
  - python -m src.gabarito.gabarito_run --label v2
"""
import json
import sys
from html import escape
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
REG = DATA / "regressao"
PUBLIC = ROOT / "votacao" / "public"

CRITERIOS = [
    "e_vilebrequin", "e_short", "tipo", "fundo_padrao", "aparencia",
    "autenticidade", "cor_bucket", "cordao_cor", "fecho", "etiqueta",
]
LABELS = {
    "e_vilebrequin": "É Vilebrequin?", "e_short": "É short?", "tipo": "Padrão",
    "fundo_padrao": "Fundo", "aparencia": "Aparência", "autenticidade": "Autenticidade",
    "cor_bucket": "Cor (bucket)", "cordao_cor": "Cordão", "fecho": "Fecho",
    "etiqueta": "Etiqueta",
}
GATE_CRITS = ("e_vilebrequin", "e_short")


def _arg(nome: str, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _norm(v) -> str:
    """None/''/ausente → 'n_a'; o resto vira string. (IA que não avaliou == n/a.)"""
    if v is None or v == "":
        return "n_a"
    return str(v)


def _carregar(p: Path, oque: str) -> dict:
    if not p.exists():
        print(f"Faltando: {p} ({oque}).")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _graded(truth_item: dict, crit: str) -> bool:
    """O humano avaliou esse critério? (presente e não-vazio; 'n_a' conta.)"""
    return crit in truth_item and truth_item[crit] not in (None, "")


def _item_100(ia_item: dict, truth_item: dict) -> bool | None:
    """Item 100% certo? Retorna None se o humano não avaliou nada do item.

    Regra do portão (combinada): se a verdade diz que o item deveria ser excluído
    de cara (e_vilebrequin='nao' ou e_short='nao'), basta a IA ACERTAR o portão —
    não exige os demais critérios.
    """
    graded = [c for c in CRITERIOS if _graded(truth_item, c)]
    if not graded:
        return None
    excluir_no_gate = truth_item.get("e_vilebrequin") == "nao" or truth_item.get("e_short") == "nao"
    if excluir_no_gate:
        alvos = [c for c in GATE_CRITS if truth_item.get(c) == "nao"]
    else:
        alvos = graded
    return all(_norm(ia_item.get(c)) == _norm(truth_item.get(c)) for c in alvos)


def main() -> None:
    from .gabarito_run import _ultima_rodada
    dataset = _arg("--dataset", "ville")
    # Auto: compara o baseline do dataset com a ÚLTIMA versão rodada. Você não
    # precisa passar --de/--para (mas pode, se quiser comparar duas específicas).
    de = _arg("--de") or f"{dataset}-baseline"
    para = _arg("--para") or _ultima_rodada(dataset)
    if not para:
        print(f"Sem rodadas pro dataset '{dataset}'. Rode gabarito_run primeiro.")
        sys.exit(0)
    if para == de:
        print(f"A última rodada de '{dataset}' É o baseline — não há versão nova pra "
              f"comparar. Edite um prompt e rode: python -m src.gabarito.gabarito_run --dataset {dataset}")
        sys.exit(0)

    truth = _carregar(REG / "gabarito_respostas.json", "gabarito (rode gabarito_export)")["respostas"]
    rodA = _carregar(REG / f"rodada-{de}.json", f"rodada {de}")
    rodB = _carregar(REG / f"rodada-{para}.json", f"rodada {para}")
    A, B = rodA["itens"], rodB["itens"]
    dataset = rodB.get("dataset", "ville")  # rodadas antigas = ville
    meta = {str(x["id"]): x for x in _carregar(PUBLIC / f"gabarito_{dataset}.json", f"gabarito_{dataset}")["itens"]}

    # Escopa aos itens DESTA rodada (a marca em questão). O /api/gabarito é
    # compartilhado entre Ville e Sundek; sem isso, respostas de uma marca
    # poluiriam o diff da outra. A (rodada) só tem os ids da marca certa.
    ids = [i for i in A if i in truth and isinstance(truth[i], dict) and truth[i]]
    if not ids:
        print("Gabarito vazio (pra esta marca) — ninguém preencheu ainda. Nada a comparar.")
        sys.exit(0)

    # ── Por área (critério) ──────────────────────────────────────────
    por_area = []  # (crit, accA, accB, n, regr[], melh[])
    for c in CRITERIOS:
        n = okA = okB = 0
        regr, melh = [], []
        for iid in ids:
            t = truth[iid]
            if not _graded(t, c):
                continue
            n += 1
            mA = _norm(A.get(iid, {}).get(c)) == _norm(t.get(c))
            mB = _norm(B.get(iid, {}).get(c)) == _norm(t.get(c))
            okA += mA
            okB += mB
            if mA and not mB:
                regr.append(iid)
            elif mB and not mA:
                melh.append(iid)
        accA = (okA / n * 100) if n else None
        accB = (okB / n * 100) if n else None
        por_area.append((c, accA, accB, n, regr, melh))

    # ── Geral (itens 100% certos) ────────────────────────────────────
    avaliaveis = [i for i in ids if _item_100(A.get(i, {}), truth[i]) is not None]
    full_A = sum(1 for i in avaliaveis if _item_100(A.get(i, {}), truth[i]))
    full_B = sum(1 for i in avaliaveis if _item_100(B.get(i, {}), truth[i]))

    # ── Console ──────────────────────────────────────────────────────
    print(f"\n=== Comparação {de} → {para} · {len(ids)} itens com gabarito ===\n")
    print(f"{'ÁREA':<16}{'n':>4}{de:>10}{para:>10}{'Δ':>8}   ")
    print("-" * 60)
    for c, accA, accB, n, regr, melh in por_area:
        if not n:
            print(f"{LABELS[c]:<16}{0:>4}{'—':>10}{'—':>10}{'—':>8}")
            continue
        delta = accB - accA
        seta = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "=")
        print(f"{LABELS[c]:<16}{n:>4}{accA:>9.0f}%{accB:>9.0f}%{delta:>+7.0f}% {seta}")
    print("-" * 60)
    print(f"{'ITENS 100% CERTOS':<16}{len(avaliaveis):>4}{full_A:>10}{full_B:>10}{full_B-full_A:>+8}")

    # detalhe das flips
    print("\n--- Mudanças por área (id · A_ia → B_ia | verdade) ---")
    for c, accA, accB, n, regr, melh in por_area:
        if not (regr or melh):
            continue
        print(f"\n[{LABELS[c]}]")
        for iid in melh:
            print(f"  ✅ MELHOROU  {iid}: {_norm(A.get(iid,{}).get(c))} → {_norm(B.get(iid,{}).get(c))} | verdade={_norm(truth[iid].get(c))}")
        for iid in regr:
            print(f"  ❌ REGREDIU  {iid}: {_norm(A.get(iid,{}).get(c))} → {_norm(B.get(iid,{}).get(c))} | verdade={_norm(truth[iid].get(c))}")

    # ── HTML ─────────────────────────────────────────────────────────
    _gerar_html(de, para, len(ids), por_area, avaliaveis, full_A, full_B, A, B, truth, meta)


def _linha_flip(tipo: str, iid: str, c: str, A, B, truth, meta) -> str:
    titulo = escape((meta.get(iid, {}).get("titulo") or "")[:60])
    url = escape(meta.get(iid, {}).get("url") or "#")
    a = escape(_norm(A.get(iid, {}).get(c)))
    b = escape(_norm(B.get(iid, {}).get(c)))
    t = escape(_norm(truth[iid].get(c)))
    cor = "#00ff88" if tipo == "melh" else "#ff4d6d"
    icone = "✅" if tipo == "melh" else "❌"
    return (f'<div style="font-size:12px;margin:2px 0">{icone} '
            f'<a href="{url}" target="_blank" style="color:#00d9ff;text-decoration:none">{iid}</a> '
            f'<span style="color:#8a8a94">{titulo}</span> — '
            f'<b style="color:{cor}">{a} → {b}</b> '
            f'<span style="color:#8a8a94">| verdade: {t}</span></div>')


def _gerar_html(de, para, n_itens, por_area, avaliaveis, full_A, full_B, A, B, truth, meta) -> None:
    linhas = []
    for c, accA, accB, n, regr, melh in por_area:
        if not n:
            linhas.append(f'<tr><td>{LABELS[c]}</td><td>0</td><td>—</td><td>—</td><td>—</td></tr>')
            continue
        delta = accB - accA
        cor = "#00ff88" if delta > 0.01 else ("#ff4d6d" if delta < -0.01 else "#8a8a94")
        seta = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "=")
        linhas.append(
            f'<tr><td>{LABELS[c]}</td><td>{n}</td><td>{accA:.0f}%</td><td>{accB:.0f}%</td>'
            f'<td style="color:{cor};font-weight:600">{delta:+.0f}% {seta}</td></tr>'
        )

    flips = []
    for c, accA, accB, n, regr, melh in por_area:
        if not (regr or melh):
            continue
        bloco = "".join(_linha_flip("melh", i, c, A, B, truth, meta) for i in melh)
        bloco += "".join(_linha_flip("regr", i, c, A, B, truth, meta) for i in regr)
        flips.append(f'<div style="margin:14px 0"><div style="font-weight:600;margin-bottom:4px">{LABELS[c]}</div>{bloco}</div>')

    geral_cor = "#00ff88" if full_B > full_A else ("#ff4d6d" if full_B < full_A else "#8a8a94")
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Regressão de prompts · {escape(de)} → {escape(para)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0e0e12;color:#f5f5f7;padding:24px 16px;max-width:900px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#b8b8c0;font-size:13px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;margin-bottom:8px}}
th,td{{text-align:left;padding:8px 10px;font-size:13px;border-bottom:1px solid rgba(255,255,255,.07)}}
th{{color:#8a8a94;font-weight:500}} td:nth-child(n+2){{text-align:right}} th:nth-child(n+2){{text-align:right}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px 18px;margin-bottom:18px}}
.big{{font-size:15px}}
</style></head><body>
<h1>Regressão de prompts · Ville</h1>
<div class="sub">{escape(de)} → {escape(para)} · {n_itens} itens com gabarito · acerto da IA contra a verdade humana</div>
<div class="card">
  <table>
    <tr><th>Área</th><th>n</th><th>{escape(de)}</th><th>{escape(para)}</th><th>Δ</th></tr>
    {''.join(linhas)}
  </table>
  <div class="big" style="margin-top:10px">Itens 100% certos:
    <b>{full_A}</b> → <b style="color:{geral_cor}">{full_B}</b>
    <span style="color:#8a8a94">de {len(avaliaveis)} avaliáveis</span>
  </div>
</div>
<div class="card">
  <div style="font-weight:600;margin-bottom:8px">Mudanças item a item</div>
  {''.join(flips) if flips else '<div style="color:#8a8a94;font-size:13px">Nenhuma mudança de acerto entre as rodadas.</div>'}
</div>
</body></html>"""
    out = REG / f"comparativo_{de}_{para}.html"
    out.write_text(html, encoding="utf-8")
    print(f"\nHTML -> {out}")


if __name__ == "__main__":
    main()
