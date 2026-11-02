"""Relatório do modo sombra: a VPS (sempre ligada) × o robô do GitHub Actions.

Lê ~/didi-sombra/vistos.jsonl e ciclos.jsonl e o acervo do GitHub (data/coleta-classificada.json
do main) e responde:
  - quanto tempo depois de publicado cada anúncio a VPS e o GitHub viram (por faixa e por hora);
  - quantos a VPS viu e o GitHub NÃO viu (ou viu horas depois) — e quais eram compráveis;
  - ciclos com bloqueio/erro da Vinted.
Uso: python -m src.worker.relatorio_sombra [--dias 7]
"""
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..build.votacao_items import _publicado_em

DIR = Path(os.environ.get("SOMBRA_DIR", Path.home() / "didi-sombra"))
ACERVO = "https://raw.githubusercontent.com/danielreinaux/didi/main/data/coleta-classificada.json"
BRT = timezone(timedelta(hours=-3))


def _dt(iso):
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def _linhas(arq: Path) -> list[dict]:
    if not arq.exists():
        return []
    out = []
    for l in arq.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def _faixa(min_):
    for lim, nome in ((5, "até 5 min"), (15, "5–15 min"), (60, "15–60 min"), (180, "1–3 h"), (10**9, "mais de 3 h")):
        if min_ < lim:
            return nome


def main() -> None:
    dias = int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 7
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    vistos = [v for v in _linhas(DIR / "vistos.jsonl") if not v.get("inicial") and (_dt(v["visto_em"]) or desde) >= desde]
    ciclos = [c for c in _linhas(DIR / "ciclos.jsonl") if (_dt(c.get("inicio", "")) or desde) >= desde]
    print(f"=== Modo sombra — últimos {dias} dias ===")
    print(f"ciclos: {len(ciclos)} | com bloqueio: {sum(1 for c in ciclos if c.get('bloqueio'))} "
          f"| com erro: {sum(1 for c in ciclos if c.get('erro'))}")
    dur = [c["duracao_s"] for c in ciclos if c.get("duracao_s")]
    if dur:
        print(f"duração do ciclo: mediana {sorted(dur)[len(dur) // 2]:.0f}s, máx {max(dur):.0f}s")
    print(f"anúncios novos vistos pela VPS: {len(vistos)}")
    seg = sorted(v["segundos_ate_decisao"] for v in vistos if v.get("decisao") and v.get("segundos_ate_decisao"))
    if seg:
        print(f"entre ver e decidir (IA): mediana {seg[len(seg) // 2]:.0f}s, 90% em até {seg[int(len(seg) * 0.9)]:.0f}s")

    with urllib.request.urlopen(ACERVO, timeout=120) as r:
        acervo = {str(i["id"]): i for i in json.loads(r.read().decode("utf-8"))}

    faixa_vps, faixa_gh = Counter(), Counter()
    so_vps, gh_atrasado, por_hora = [], [], Counter()
    antigos = 0
    for v in vistos:
        visto_vps = _dt(v["visto_em"])
        pub = _publicado_em({"upload": v.get("upload"), "coletado_em": v.get("coletado_em") or v["visto_em"]})
        pub = _dt(pub) if pub else None
        if pub and visto_vps - pub > timedelta(hours=24):
            antigos += 1  # anúncio antigo "subido" pelo vendedor: fora da comparação
            continue
        if pub:
            faixa_vps[_faixa((visto_vps - pub).total_seconds() / 60)] += 1
        gh = acervo.get(str(v["id"]))
        pv = _dt(gh.get("primeiro_visto")) if gh else None
        if pv is None:
            so_vps.append(v)
            continue
        if pub:
            faixa_gh[_faixa((pv - pub).total_seconds() / 60)] += 1
        adiant = (pv - visto_vps).total_seconds() / 60
        if adiant >= 30:
            gh_atrasado.append((v, adiant))
            por_hora[visto_vps.astimezone(BRT).hour] += 1

    ordem = ["até 5 min", "5–15 min", "15–60 min", "1–3 h", "mais de 3 h"]
    print(f"(fora da comparação: {antigos} anúncios antigos que o vendedor subiu de novo)")
    print("\nTempo entre publicar e ver (VPS × GitHub), anúncios de até 24 h:")
    for f in ordem:
        print(f"  {f:12} VPS {faixa_vps[f]:4}   GitHub {faixa_gh[f]:4}")
    print(f"\nA VPS viu e o GitHub nunca viu: {len(so_vps)}")
    print(f"A VPS viu 30+ min antes do GitHub: {len(gh_atrasado)}")
    if por_hora:
        print("  por hora (BRT):", ", ".join(f"{h:02d}h={n}" for h, n in sorted(por_hora.items())))
    bons = [v for v in so_vps + [x for x, _ in gh_atrasado] if v.get("decisao") in ("compravel", "medio")]
    print(f"\nCompráveis/barganhas que a VPS pegou antes (ou sozinha): {len(bons)}")
    for v in bons[:20]:
        print(f"  {v['visto_em'][:16]}Z {v.get('decisao'):9} {v.get('preco')} {v.get('tamanho')} | {(v.get('titulo') or '')[:45]} | {v['url']}")


if __name__ == "__main__":
    main()
