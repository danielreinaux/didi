"""Gera data/relatorio-custo.html — relatório consolidado de tokens e custo.

Fonte de dados: o PRÓPRIO histórico do git. Cada run do cron sobrescreve e
commita data/custo_por_etapa.json (Sundek) e, daqui pra frente, data/custo_ville.json
(Ville). Como o cost_tracker zera a cada processo, cada snapshot commitado = o custo
DAQUELE run. Então varremos todos os commits desses arquivos e somamos.

O que ele responde:
  - Total de TOKENS IN / OUT / chamadas / custo (USD e R$), Sundek + Ville
  - Quebra por dia, por modelo e por etapa
  - Quais runs "deram pau / não processaram nada" (snapshot vazio {} ou 0 chamadas)

Uso:  python -m src.build.relatorio_custo
      (só lê o git — não precisa de rede, API ou deploy)

⚠️ Ville: o custo do Ville é PISO — o ville_run.py hoje preça tudo como gpt-4o-mini,
mas ele também usa gpt-4o em vários passos (marca/tartaruga/autenticidade/fecho),
que custa ~17x mais. O relatório sinaliza isso. Ver docs pra correção definitiva.
"""
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path

from ..utils.cost_tracker import PRECOS

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

# Brasil não tem horário de verão desde 2019 → offset fixo -03:00 (evita depender
# de tzdata no Windows). Usado só pra agrupar os runs por dia "do Brasil".
BRT = timezone(timedelta(hours=-3))
USD_BRL = 5.0  # mesma taxa que o resto do pipeline usa nos resumos

SUNDEK_FILE = "data/custo_por_etapa.json"
VILLE_FILE = "data/custo_ville.json"


# ─────────────────────────────────────────────────────────────────────────────
# Leitura do git
# ─────────────────────────────────────────────────────────────────────────────
def _git(*args: str) -> str:
    """Roda um comando git na raiz do repo e devolve stdout (texto)."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout


def _snapshots(relpath: str) -> list[tuple[datetime, str]]:
    """Devolve [(data_commit, conteudo_json)] de cada versão commitada do arquivo,
    em ordem cronológica (mais antigo → mais novo)."""
    log = _git("log", "--format=%H%x09%cI", "--", relpath).strip()
    if not log:
        return []
    linhas = [l for l in log.splitlines() if l.strip()]
    snaps: list[tuple[datetime, str]] = []
    for linha in linhas:
        sha, iso = linha.split("\t", 1)
        conteudo = _git("show", f"{sha}:{relpath}")
        try:
            dt = datetime.fromisoformat(iso).astimezone(BRT)
        except ValueError:
            continue
        snaps.append((dt, conteudo))
    snaps.reverse()  # log vem do mais novo pro mais antigo
    return snaps


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de custo
# ─────────────────────────────────────────────────────────────────────────────
def _custo(modelo: str, tin: int, tout: int) -> float:
    """USD de uma chamada, usando a tabela de preços do cost_tracker.
    Modelo desconhecido → 0 (e some no total, mas sinalizamos na quebra por modelo)."""
    p = PRECOS.get(modelo, {"in": 0.0, "out": 0.0})
    return (tin / 1_000_000) * p["in"] + (tout / 1_000_000) * p["out"]


def _parse_sundek(raw: str) -> dict:
    """custo_por_etapa.json → {tok_in, tok_out, calls, custo, por_etapa, por_modelo, vazio}."""
    try:
        d = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        d = {}
    por_etapa: dict[str, dict] = {}
    por_modelo: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "custo": 0.0})
    tin = tout = calls = 0
    custo = 0.0
    for etapa, modelos in d.items():
        e_tin = e_tout = e_calls = 0
        e_custo = 0.0
        for modelo, v in modelos.items():
            c = _custo(modelo, v["in"], v["out"])
            e_tin += v["in"]; e_tout += v["out"]; e_calls += v["calls"]; e_custo += c
            m = por_modelo[modelo]
            m["in"] += v["in"]; m["out"] += v["out"]; m["calls"] += v["calls"]; m["custo"] += c
        por_etapa[etapa] = {"in": e_tin, "out": e_tout, "calls": e_calls, "custo": e_custo}
        tin += e_tin; tout += e_tout; calls += e_calls; custo += e_custo
    return {"tok_in": tin, "tok_out": tout, "calls": calls, "custo": custo,
            "por_etapa": por_etapa, "por_modelo": dict(por_modelo),
            "vazio": (calls == 0)}


def _parse_ville(raw: str) -> dict:
    """custo_ville.json (formato novo, gravado pelo ville_run) → mesma cara do Sundek.
    Estrutura esperada: {tok_in, tok_out, calls, custo_usd, itens_processados, duracao_s}.
    Custo é PISO (preço mini) — sinalizado no relatório."""
    try:
        d = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        d = {}
    tin = int(d.get("tok_in", 0)); tout = int(d.get("tok_out", 0))
    calls = int(d.get("calls", 0)); custo = float(d.get("custo_usd", 0.0))
    itens = int(d.get("itens_processados", 0))
    # Sem quebra por etapa (ville_run só tem o total); modelo entra como rótulo único.
    por_modelo = {}
    if tin or tout:
        por_modelo = {"ville (piso mini)": {"in": tin, "out": tout, "calls": calls, "custo": custo}}
    return {"tok_in": tin, "tok_out": tout, "calls": calls, "custo": custo,
            "por_etapa": {}, "por_modelo": por_modelo,
            "vazio": (itens == 0 and tin == 0)}


def _coletar() -> list[dict]:
    """Junta todos os runs (Sundek + Ville) numa lista de eventos com data e marca."""
    runs: list[dict] = []
    for dt, raw in _snapshots(SUNDEK_FILE):
        r = _parse_sundek(raw); r["dt"] = dt; r["marca"] = "Sundek"
        runs.append(r)
    for dt, raw in _snapshots(VILLE_FILE):
        r = _parse_ville(raw); r["dt"] = dt; r["marca"] = "Ville"
        runs.append(r)
    runs.sort(key=lambda r: r["dt"])
    return runs


# ─────────────────────────────────────────────────────────────────────────────
# Agregações
# ─────────────────────────────────────────────────────────────────────────────
def _agregar(runs: list[dict]) -> dict:
    tot = {"tok_in": 0, "tok_out": 0, "calls": 0, "custo": 0.0}
    por_dia: dict[str, dict] = defaultdict(lambda: {"Sundek": 0.0, "Ville": 0.0})
    por_modelo: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "custo": 0.0})
    por_etapa: dict[str, dict] = defaultdict(lambda: {"in": 0, "out": 0, "calls": 0, "custo": 0.0})
    vazios: list[dict] = []

    for r in runs:
        tot["tok_in"] += r["tok_in"]; tot["tok_out"] += r["tok_out"]
        tot["calls"] += r["calls"]; tot["custo"] += r["custo"]
        dia = r["dt"].strftime("%Y-%m-%d")
        por_dia[dia][r["marca"]] += r["custo"]
        for modelo, v in r["por_modelo"].items():
            m = por_modelo[modelo]
            m["in"] += v["in"]; m["out"] += v["out"]; m["calls"] += v["calls"]; m["custo"] += v["custo"]
        for etapa, v in r["por_etapa"].items():
            e = por_etapa[etapa]
            e["in"] += v["in"]; e["out"] += v["out"]; e["calls"] += v["calls"]; e["custo"] += v["custo"]
        if r["vazio"]:
            vazios.append(r)

    return {"tot": tot, "por_dia": dict(por_dia), "por_modelo": dict(por_modelo),
            "por_etapa": dict(por_etapa), "vazios": vazios,
            "n_runs": len(runs), "n_ok": len(runs) - len(vazios)}


# ─────────────────────────────────────────────────────────────────────────────
# Render HTML (mesmo visual claro de analise.html)
# ─────────────────────────────────────────────────────────────────────────────
def _stat(valor: str, label: str, cls: str = "") -> str:
    return f'<div class="stat {cls}"><div class="v">{valor}</div><div class="l">{escape(label)}</div></div>'


def _chart_dias(por_dia: dict[str, dict]) -> str:
    """Barras SVG de custo/dia (Sundek em azul, Ville em âmbar, empilhados)."""
    if not por_dia:
        return "<p class='vazio'>Sem dados de custo por dia ainda.</p>"
    dias = sorted(por_dia)
    maximo = max((d["Sundek"] + d["Ville"]) for d in por_dia.values()) or 1e-9
    larg, alt, pad_b = 34, 180, 46
    gap = 8
    total_w = max(len(dias) * (larg + gap) + 40, 320)
    barras = []
    for i, dia in enumerate(dias):
        x = 30 + i * (larg + gap)
        s = por_dia[dia]["Sundek"]; v = por_dia[dia]["Ville"]
        h_s = (s / maximo) * alt
        h_v = (v / maximo) * alt
        y_s = 10 + alt - h_s
        y_v = y_s - h_v
        total = s + v
        barras.append(
            f'<g><title>{dia}: ${total:.4f} (Sundek ${s:.4f} / Ville ${v:.4f})</title>'
            f'<rect x="{x}" y="{y_s:.1f}" width="{larg}" height="{h_s:.1f}" fill="#2563eb" rx="2"/>'
            f'<rect x="{x}" y="{y_v:.1f}" width="{larg}" height="{h_v:.1f}" fill="#a16207" rx="2"/>'
            f'<text x="{x + larg/2:.0f}" y="{10 + alt + 14}" font-size="9" fill="#71717a" '
            f'text-anchor="middle" transform="rotate(35 {x + larg/2:.0f} {10 + alt + 14})">{dia[5:]}</text>'
            f'</g>'
        )
    return (
        f'<svg viewBox="0 0 {total_w} {alt + pad_b + 20}" width="100%" '
        f'style="max-width:{total_w}px">{"".join(barras)}'
        f'<line x1="30" y1="{10 + alt}" x2="{total_w}" y2="{10 + alt}" stroke="#d4d4d8"/>'
        f'</svg>'
        f'<div class="legenda-chart"><span class="dot" style="background:#2563eb"></span>Sundek '
        f'<span class="dot" style="background:#a16207"></span>Ville (piso)</div>'
    )


def _tabela_modelo(por_modelo: dict) -> str:
    linhas = []
    for modelo, v in sorted(por_modelo.items(), key=lambda kv: -kv[1]["custo"]):
        desconhecido = modelo not in PRECOS and "piso" not in modelo
        aviso = ' <span class="warn">preço 0 (modelo fora da tabela)</span>' if desconhecido else ""
        linhas.append(
            f'<tr><td>{escape(modelo)}{aviso}</td><td>{v["calls"]:,}</td>'
            f'<td>{v["in"]:,}</td><td>{v["out"]:,}</td><td>${v["custo"]:.4f}</td></tr>'
        )
    return (
        '<table><thead><tr><th>Modelo</th><th>Chamadas</th><th>Tok IN</th>'
        f'<th>Tok OUT</th><th>Custo</th></tr></thead><tbody>{"".join(linhas)}</tbody></table>'
    )


def _tabela_etapa(por_etapa: dict) -> str:
    if not por_etapa:
        return "<p class='vazio'>Sem quebra por etapa (só o Sundek fornece isso).</p>"
    linhas = []
    for etapa, v in sorted(por_etapa.items(), key=lambda kv: -kv[1]["custo"]):
        linhas.append(
            f'<tr><td>{escape(etapa)}</td><td>{v["calls"]:,}</td>'
            f'<td>{v["in"]:,}</td><td>{v["out"]:,}</td><td>${v["custo"]:.4f}</td></tr>'
        )
    return (
        '<table><thead><tr><th>Etapa (Sundek)</th><th>Chamadas</th><th>Tok IN</th>'
        f'<th>Tok OUT</th><th>Custo</th></tr></thead><tbody>{"".join(linhas)}</tbody></table>'
    )


def _tabela_vazios(vazios: list[dict]) -> str:
    if not vazios:
        return "<p class='vazio'>Nenhum run vazio detectado. 🎉</p>"
    linhas = []
    for r in vazios:
        linhas.append(
            f'<tr><td>{r["dt"].strftime("%d/%m/%Y %H:%M")}</td><td>{r["marca"]}</td>'
            f'<td>0 chamadas / snapshot vazio</td></tr>'
        )
    return (
        '<table><thead><tr><th>Quando (BRT)</th><th>Marca</th><th>Motivo</th></tr></thead>'
        f'<tbody>{"".join(linhas)}</tbody></table>'
    )


def _render(runs: list[dict], ag: dict) -> str:
    tot = ag["tot"]
    custo_brl = tot["custo"] * USD_BRL
    periodo = "sem dados"
    if runs:
        periodo = f'{runs[0]["dt"].strftime("%d/%m/%Y")} → {runs[-1]["dt"].strftime("%d/%m/%Y")}'
    tem_ville = any(r["marca"] == "Ville" for r in runs)
    nota_ville = "" if tem_ville else (
        '<div class="nota">⚠️ Ville ainda sem histórico no git — vai começar a aparecer '
        'depois que o gancho de gravação de custo do <code>ville_run.py</code> subir pro cron.</div>'
    )
    gerado = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")

    cards = "".join([
        _stat(f"${tot['custo']:.4f}", "Custo total (USD)"),
        _stat(f"R$ {custo_brl:.2f}", f"Custo total (~R$ {USD_BRL:.0f}/USD)"),
        _stat(f"{tot['tok_in']:,}", "Tokens IN"),
        _stat(f"{tot['tok_out']:,}", "Tokens OUT"),
        _stat(f"{tot['calls']:,}", "Chamadas à API"),
        _stat(f"{ag['n_ok']}", "Runs com processamento", "ok"),
        _stat(f"{len(ag['vazios'])}", "Runs vazios / deu pau", "x" if ag["vazios"] else ""),
    ])

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório de custo — Didi</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#f2f2f0; color:#18181b; padding:20px 14px 60px; }}
.container {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:24px; margin-bottom:6px; }}
h2 {{ font-size:16px; margin:24px 0 10px; color:#52525b; }}
.sub-h {{ color:#666; font-size:13px; margin-bottom:18px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:10px; margin-bottom:8px; }}
.stat {{ background:#fff; border:1px solid #e4e4e7; border-radius:10px; padding:12px; }}
.stat .v {{ font-size:22px; font-weight:700; }}
.stat .l {{ font-size:12px; color:#71717a; margin-top:4px; }}
.stat.ok .v {{ color:#15803d; }}
.stat.x .v {{ color:#7f1d1d; }}
.card {{ background:#fff; border:1px solid #e4e4e7; border-radius:10px; padding:16px; margin-bottom:16px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th,td {{ padding:7px 8px; border-bottom:1px solid #f0f0f0; text-align:left; }}
th {{ color:#71717a; font-weight:600; font-size:12px; }}
td:nth-child(n+2), th:nth-child(n+2) {{ text-align:right; }}
.warn {{ color:#b45309; font-size:11px; }}
.vazio {{ color:#71717a; font-size:13px; }}
.nota {{ background:#fffbeb; border:1px solid #fde68a; color:#92400e; border-radius:8px;
  padding:10px 12px; font-size:13px; margin-bottom:16px; }}
.legenda-chart {{ font-size:12px; color:#71717a; margin-top:8px; }}
.legenda-chart .dot {{ display:inline-block; width:10px; height:10px; border-radius:2px;
  margin:0 4px 0 12px; vertical-align:middle; }}
code {{ background:#f4f4f5; padding:1px 5px; border-radius:3px; font-size:12px; }}
</style></head><body><div class="container">
<h1>💰 Relatório de custo — Sundek + Ville</h1>
<p class="sub-h">Período: {periodo} · {ag['n_runs']} runs · gerado em {gerado} (BRT) · fonte: histórico do git</p>
{nota_ville}
<div class="stats">{cards}</div>

<h2>Custo por dia</h2>
<div class="card">{_chart_dias(ag['por_dia'])}</div>

<h2>Por modelo</h2>
<div class="card">{_tabela_modelo(ag['por_modelo'])}</div>

<h2>Por etapa</h2>
<div class="card">{_tabela_etapa(ag['por_etapa'])}</div>

<h2>Runs que deram pau / não processaram nada</h2>
<div class="card">{_tabela_vazios(ag['vazios'])}</div>

<div class="nota">Custo do Ville é <b>piso</b>: o <code>ville_run.py</code> preça tudo como
gpt-4o-mini, mas usa gpt-4o (17x mais caro) em marca/tartaruga/autenticidade/fecho.
O número real do Ville é maior.</div>
</div></body></html>"""


def main() -> None:
    runs = _coletar()
    ag = _agregar(runs)
    saida = DATA / "relatorio-custo.html"
    saida.write_text(_render(runs, ag), encoding="utf-8")

    # Resumo no terminal também (rápido de olhar sem abrir o HTML)
    tot = ag["tot"]
    print(f"\n=== Relatório de custo ({ag['n_runs']} runs) ===")
    print(f"  Custo total:  ${tot['custo']:.4f}  (~R$ {tot['custo'] * USD_BRL:.2f})")
    print(f"  Tokens IN:    {tot['tok_in']:,}")
    print(f"  Tokens OUT:   {tot['tok_out']:,}")
    print(f"  Chamadas:     {tot['calls']:,}")
    print(f"  Runs vazios:  {len(ag['vazios'])} de {ag['n_runs']}")
    print(f"\n  HTML salvo em {saida}")


if __name__ == "__main__":
    main()
