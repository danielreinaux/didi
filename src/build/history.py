"""Gera o histórico de rodadas pra rota /history do app de votação.

Cada RODADA = 1 workflow run do GitHub (scrape-cron.yml). A saída é estática:

  votacao/public/history/index.json       → lista resumida das últimas N rodadas
  votacao/public/history/<run_id>.json     → 1 arquivo por rodada, com métricas
                                             completas + produtos (candidatos +
                                             descartados ainda à venda) e, por
                                             produto, todos os critérios que a IA
                                             avaliou + a composição da pontuação.

Dois modos:

  • snapshot (default) — lê o working-tree JÁ commitado (data/coleta-classificada.json,
    data/coleta-ville-classificada.json, data/custo_por_etapa.json, data/custo_ville.json)
    e gera o snapshot DESTA rodada. É o modo usado no job `deploy` do cron
    (run_id = $GITHUB_RUN_ID). Só stdlib — não precisa de pip install.

  • --backfill [N] — varre o histórico do GIT (como o relatorio_custo.py) e
    reconstrói as últimas N rodadas a partir dos commits do cron. Rode LOCAL uma
    vez pra semear o histórico. Cada commit de coleta-classificada.json (Sundek) é
    uma rodada; a Ville é pareada pelo commit mais próximo no tempo.

Uso:
  python -m src.build.history                 # snapshot da rodada atual (working-tree)
  python -m src.build.history --backfill 25   # semeia as últimas 25 rodadas do git
  python -m src.build.history --backfill 25 --clean   # idem, limpando a pasta antes
"""
import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT_DIR = ROOT / "votacao" / "public" / "history"

# Espelha src.utils.cost_tracker.PRECOS. Embutido aqui de propósito: o job `deploy`
# do cron roda este builder SEM `pip install`, então não podemos depender de nada
# fora da stdlib. Se a tabela de lá mudar, atualizar aqui também.
PRECOS = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}
USD_BRL = 5.0  # mesma taxa que o resto do pipeline usa nos resumos

# Brasil sem horário de verão desde 2019 → offset fixo -03:00 (não depende de tzdata).
BRT = timezone(timedelta(hours=-3))

# Quanto do acervo ativo entra no arquivo por produto. Candidatos entram SEMPRE
# (são poucos). Descartados/não-classificados são muitos (acervo acumulado), então
# só os "melhores por score" entram — o resto vira contagem nas métricas (nada é
# escondido em silêncio: `produtos_info` diz quantos ficaram de fora).
MAX_DESCARTADOS_POR_MARCA = 120
MAX_NAO_CLASSIF_POR_MARCA = 40
MAX_FOTOS = 4
# "Novo nesta rodada" = primeiro_visto dentro dessa janela antes do horário da rodada
# (cadência do cron é 40 min; margem folgada pra não perder itens da rodada).
JANELA_NOVOS_MIN = 55
# Teto de rodadas no index.json (as mais recentes). É uma JANELA DESLIZANTE: o modo
# snapshot (cron) mantém as N mais novas e poda os arquivos excedentes. 200 segura o
# backfill completo (~97 rodadas hoje) + vários dias de cron antes de começar a podar.
# Dá pra sobrescrever por rodada com --max-runs.
MAX_RUNS_INDEX = 200

SUNDEK_CLASSIF = "data/coleta-classificada.json"
VILLE_CLASSIF = "data/coleta-ville-classificada.json"
SUNDEK_CUSTO = "data/custo_por_etapa.json"
VILLE_CUSTO = "data/custo_ville.json"

# Blocos de critério que a IA preenche por item (Sundek + Ville). Só os presentes
# entram no produto — cada um traz justificativa/evidencia/confianca pro detalhe.
CRITERIOS_KEYS = [
    "cor", "elastico", "etiqueta", "classificacao",              # Sundek
    "marca_check", "tartaruga", "autenticidade", "cordao", "fecho",  # Ville
]


# ─────────────────────────────────────────────────────────────────────────────
# Leitura (working-tree e git)
# ─────────────────────────────────────────────────────────────────────────────
def _git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout


def _load_json(raw: str) -> object:
    try:
        return json.loads(raw) if raw and raw.strip() else None
    except json.JSONDecodeError:
        return None


def _read_working(relpath: str) -> object:
    p = ROOT / relpath
    if not p.exists():
        return None
    return _load_json(p.read_text(encoding="utf-8"))


def _commits(relpath: str, n: int) -> list[tuple[str, datetime]]:
    """Últimos n commits que tocaram relpath, mais novo → mais antigo: [(sha, dt_brt)]."""
    log = _git("log", f"-n{n}", "--format=%H%x09%cI", "--", relpath).strip()
    saida: list[tuple[str, datetime]] = []
    for linha in log.splitlines():
        if "\t" not in linha:
            continue
        sha, iso = linha.split("\t", 1)
        try:
            dt = datetime.fromisoformat(iso).astimezone(BRT)
        except ValueError:
            continue
        saida.append((sha, dt))
    return saida


def _show_json(sha: str, relpath: str) -> object:
    return _load_json(_git("show", f"{sha}:{relpath}"))


# ─────────────────────────────────────────────────────────────────────────────
# Custo
# ─────────────────────────────────────────────────────────────────────────────
def _custo_chamada(modelo: str, tin: int, tout: int) -> float:
    p = PRECOS.get(modelo, {"in": 0.0, "out": 0.0})
    return (tin / 1_000_000) * p["in"] + (tout / 1_000_000) * p["out"]


def _custo_sundek(d: object) -> dict:
    """custo_por_etapa.json → totais + quebra por etapa."""
    base = {"tok_in": 0, "tok_out": 0, "calls": 0, "custo_usd": 0.0, "por_etapa": {}}
    if not isinstance(d, dict):
        return base
    for etapa, modelos in d.items():
        if not isinstance(modelos, dict):
            continue
        e_in = e_out = e_calls = 0
        e_custo = 0.0
        for modelo, v in modelos.items():
            vin, vout, vc = int(v.get("in", 0)), int(v.get("out", 0)), int(v.get("calls", 0))
            e_in += vin; e_out += vout; e_calls += vc
            e_custo += _custo_chamada(modelo, vin, vout)
        base["por_etapa"][etapa] = {"tok_in": e_in, "tok_out": e_out,
                                    "calls": e_calls, "custo_usd": round(e_custo, 6)}
        base["tok_in"] += e_in; base["tok_out"] += e_out
        base["calls"] += e_calls; base["custo_usd"] += e_custo
    base["custo_usd"] = round(base["custo_usd"], 6)
    return base


def _custo_ville(d: object) -> dict:
    """custo_ville.json (formato do ville_run) → totais. Custo é PISO (preço mini)."""
    base = {"tok_in": 0, "tok_out": 0, "calls": 0, "custo_usd": 0.0,
            "por_etapa": {}, "duracao_s": None, "custo_piso": True}
    if not isinstance(d, dict):
        return base
    base["tok_in"] = int(d.get("tok_in", 0))
    base["tok_out"] = int(d.get("tok_out", 0))
    base["calls"] = int(d.get("calls", 0))
    base["custo_usd"] = round(float(d.get("custo_usd", 0.0)), 6)
    base["duracao_s"] = d.get("duracao_s")
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Produtos e métricas
# ─────────────────────────────────────────────────────────────────────────────
def _decisao(it: dict) -> str:
    return (it.get("score") or {}).get("decisao") or "nao_classificado"


def _ativo(it: dict) -> bool:
    return it.get("status") not in ("vendido", "inativo", "removido")


def _e_novo(it: dict, run_dt: datetime) -> bool:
    """True se primeiro_visto cai na janela desta rodada (item recém-descoberto)."""
    pv = it.get("primeiro_visto")
    if not pv:
        return False
    try:
        dt = datetime.fromisoformat(pv).astimezone(BRT)
    except (ValueError, TypeError):
        return False
    return timedelta(0) <= (run_dt - dt) <= timedelta(minutes=JANELA_NOVOS_MIN)


def _slim_produto(it: dict, marca: str, run_dt: datetime) -> dict:
    """Produto enxuto pro front: metadados + score completo + critérios da IA."""
    sc = it.get("score") or {}
    criterios = {k: it[k] for k in CRITERIOS_KEYS if isinstance(it.get(k), dict) and it.get(k)}
    return {
        "id": str(it.get("id") or ""),
        "marca": marca,
        "url": it.get("url") or "",
        "titulo": it.get("titulo") or "(sem título)",
        "tamanho": it.get("tamanho") or "?",
        "estado": it.get("estado") or "",
        "preco": it.get("preco") or "",
        "preco_total": it.get("preco_total") or it.get("preco") or "",
        "fotos": (it.get("fotos") or [])[:MAX_FOTOS],
        "coletado_em": it.get("coletado_em"),
        "primeiro_visto": it.get("primeiro_visto"),
        "status": it.get("status") or "ativo",
        "novo": _e_novo(it, run_dt),
        # Composição da pontuação (o miolo da página de produto).
        "decisao": sc.get("decisao") or "nao_classificado",
        "score": sc.get("score", 0),
        "teto": sc.get("teto"),
        "motivo": sc.get("motivo") or "",
        "motivo_exclusao": sc.get("motivo_exclusao") or "",
        "breakdown": sc.get("breakdown") or {},
        "flags": sc.get("flags") or [],
        "negociacao": sc.get("negociacao") or {},
        # Todos os critérios que a IA avaliou (cor, tartaruga, autenticidade, etc.).
        "criterios": criterios,
    }


def _metricas_marca(itens: list[dict], custo: dict, run_dt: datetime) -> dict:
    """Métricas da marca: estado do acervo + números DESTA rodada (custo/novos)."""
    ativos = [it for it in itens if _ativo(it)]
    dec = Counter(_decisao(it) for it in ativos)
    por_motivo: Counter = Counter()
    for it in ativos:
        if _decisao(it) == "descartado":
            mot = (it.get("score") or {}).get("motivo_exclusao") or ""
            for tok in [m.strip() for m in mot.split(",") if m.strip()]:
                por_motivo[tok] += 1
    novos = sum(1 for it in ativos if _e_novo(it, run_dt))
    status = Counter(it.get("status") or "ativo" for it in itens)
    compraveis = dec.get("compravel", 0)
    barganha = dec.get("medio", 0)
    return {
        # Estado do acervo (acumulado, ainda à venda)
        "acervo_total": len(itens),
        "ativos": len(ativos),
        "vendidos": status.get("vendido", 0),
        "removidos": status.get("removido", 0),
        "candidatos": compraveis + barganha,
        "compraveis": compraveis,
        "barganha": barganha,
        "descartados": dec.get("descartado", 0),
        "nao_classificados": dec.get("nao_classificado", 0),
        "por_motivo": dict(por_motivo.most_common()),
        # Desta rodada
        "novos": novos,
        "custo_usd": round(custo.get("custo_usd", 0.0), 6),
        "custo_brl": round(custo.get("custo_usd", 0.0) * USD_BRL, 2),
        "tok_in": custo.get("tok_in", 0),
        "tok_out": custo.get("tok_out", 0),
        "calls": custo.get("calls", 0),
        "duracao_s": custo.get("duracao_s"),
        "custo_piso": custo.get("custo_piso", False),
        "por_etapa": custo.get("por_etapa", {}),
    }


def _selecionar_produtos(itens: list[dict], marca: str, run_dt: datetime) -> tuple[list[dict], dict]:
    """Candidatos (todos) + top descartados/não-classificados por score. Só ativos."""
    ativos = [it for it in itens if _ativo(it)]
    def score_of(it):
        return (it.get("score") or {}).get("score", 0) or 0

    candidatos = [it for it in ativos if _decisao(it) in ("compravel", "medio")]
    descartados = [it for it in ativos if _decisao(it) == "descartado"]
    nao_class = [it for it in ativos if _decisao(it) == "nao_classificado"]

    candidatos.sort(key=lambda it: (0 if _decisao(it) == "compravel" else 1, -score_of(it)))
    descartados.sort(key=score_of, reverse=True)
    nao_class.sort(key=score_of, reverse=True)

    desc_inc = descartados[:MAX_DESCARTADOS_POR_MARCA]
    nc_inc = nao_class[:MAX_NAO_CLASSIF_POR_MARCA]

    escolhidos = candidatos + desc_inc + nc_inc
    produtos = [_slim_produto(it, marca, run_dt) for it in escolhidos]
    info = {
        "candidatos": len(candidatos),
        "descartados_total": len(descartados),
        "descartados_incluidos": len(desc_inc),
        "nao_classificados_total": len(nao_class),
        "nao_classificados_incluidos": len(nc_inc),
    }
    return produtos, info


# ─────────────────────────────────────────────────────────────────────────────
# Montagem do snapshot de uma rodada
# ─────────────────────────────────────────────────────────────────────────────
def _agregar_total(m_sundek: dict | None, m_ville: dict | None) -> dict:
    campos_soma = ["acervo_total", "ativos", "vendidos", "removidos", "candidatos",
                   "compraveis", "barganha", "descartados", "nao_classificados",
                   "novos", "tok_in", "tok_out", "calls"]
    total = {c: 0 for c in campos_soma}
    total["custo_usd"] = 0.0
    for m in (m_sundek, m_ville):
        if not m:
            continue
        for c in campos_soma:
            total[c] += m.get(c, 0) or 0
        total["custo_usd"] += m.get("custo_usd", 0.0) or 0.0
    total["custo_usd"] = round(total["custo_usd"], 6)
    total["custo_brl"] = round(total["custo_usd"] * USD_BRL, 2)
    return total


def _montar_snapshot(run_id: str, fonte: str, run_dt: datetime,
                     sundek_itens, ville_itens,
                     custo_sundek_raw, custo_ville_raw,
                     commit: dict) -> dict:
    marcas: list[str] = []
    metricas: dict = {}
    produtos: list[dict] = []
    produtos_info: dict = {}

    if isinstance(sundek_itens, list) and sundek_itens:
        marcas.append("sundek")
        custo = _custo_sundek(custo_sundek_raw)
        metricas["sundek"] = _metricas_marca(sundek_itens, custo, run_dt)
        p, info = _selecionar_produtos(sundek_itens, "sundek", run_dt)
        produtos += p
        produtos_info["sundek"] = info

    if isinstance(ville_itens, list) and ville_itens:
        marcas.append("vilebrequin")
        custo = _custo_ville(custo_ville_raw)
        metricas["vilebrequin"] = _metricas_marca(ville_itens, custo, run_dt)
        p, info = _selecionar_produtos(ville_itens, "vilebrequin", run_dt)
        produtos += p
        produtos_info["vilebrequin"] = info

    metricas["total"] = _agregar_total(metricas.get("sundek"), metricas.get("vilebrequin"))

    return {
        "run_id": run_id,
        "fonte": fonte,
        "quando": run_dt.isoformat(),
        "commit": commit,
        "marcas": marcas,
        "metricas": metricas,
        "produtos_info": produtos_info,
        "produtos": produtos,
    }


def _resumo_index(snap: dict) -> dict:
    """Linha do index.json (sem produtos — só o cabeçalho da rodada)."""
    t = snap["metricas"].get("total", {})
    return {
        "run_id": snap["run_id"],
        "fonte": snap["fonte"],
        "quando": snap["quando"],
        "marcas": snap["marcas"],
        "resumo": {
            "candidatos": t.get("candidatos", 0),
            "compraveis": t.get("compraveis", 0),
            "barganha": t.get("barganha", 0),
            "descartados": t.get("descartados", 0),
            "nao_classificados": t.get("nao_classificados", 0),
            "novos": t.get("novos", 0),
            "ativos": t.get("ativos", 0),
            "custo_usd": t.get("custo_usd", 0.0),
            "custo_brl": t.get("custo_brl", 0.0),
            "tok_in": t.get("tok_in", 0),
            "tok_out": t.get("tok_out", 0),
            "calls": t.get("calls", 0),
        },
    }


def _escrever_snapshot(snap: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{snap['run_id']}.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _build_produtos() -> int:
    """Índice global de busca: TODOS os produtos do acervo ATUAL (working-tree), com
    detalhe completo, pra busca cross-rodada em /history. Reescreve produtos.json.

    Diferente dos snapshots por rodada (que só amostram os descartados), aqui entra o
    acervo inteiro — pra você achar QUALQUER anúncio por título, descrição ou link e
    ver o motivo direto, sem entrar rodada por rodada. É o estado mais recente do item.
    """
    now = datetime.now(BRT)
    entries: list[dict] = []
    vistos: set[str] = set()
    for path, marca in ((SUNDEK_CLASSIF, "sundek"), (VILLE_CLASSIF, "vilebrequin")):
        itens = _read_working(path)
        if not isinstance(itens, list):
            continue
        for it in itens:
            id_ = str(it.get("id") or "")
            if not id_ or id_ in vistos:
                continue
            vistos.add(id_)
            e = _slim_produto(it, marca, now)
            resumo = (it.get("resumo") or "").strip()
            e["resumo"] = resumo[:280]
            # Campo único e minúsculo pra busca client-side (título + descrição + link).
            e["busca"] = " ".join(x for x in (e["titulo"], resumo, e["url"]) if x).lower()
            entries.append(e)

    # Candidatos primeiro, depois por score desc (resultado de busca já sai ranqueado).
    def _ordem(x: dict):
        d = x["decisao"]
        rank = 0 if d == "compravel" else 1 if d == "medio" else 2 if d == "descartado" else 3
        return (rank, -(x.get("score") or 0))
    entries.sort(key=_ordem)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "produtos.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return len(entries)


def _reescrever_index(resumos: list[dict], max_runs: int = MAX_RUNS_INDEX) -> list[dict]:
    """Ordena por data desc, deduplica por run_id, corta em max_runs."""
    vistos: set[str] = set()
    limpos: list[dict] = []
    for r in sorted(resumos, key=lambda x: x.get("quando", ""), reverse=True):
        rid = r.get("run_id")
        if rid in vistos:
            continue
        vistos.add(rid)
        limpos.append(r)
    limpos = limpos[:max_runs]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.json").write_text(
        json.dumps(limpos, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return limpos


def _index_atual() -> list[dict]:
    p = OUT_DIR / "index.json"
    if not p.exists():
        return []
    data = _load_json(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _prune_orfaos(ids_validos: set[str]) -> None:
    """Remove arquivos <run_id>.json que saíram do index (mantém a pasta enxuta)."""
    if not OUT_DIR.exists():
        return
    for f in OUT_DIR.glob("*.json"):
        if f.name == "index.json":
            continue
        if f.stem not in ids_validos:
            f.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# Modos
# ─────────────────────────────────────────────────────────────────────────────
def snapshot(max_runs: int = MAX_RUNS_INDEX) -> None:
    """Snapshot da rodada ATUAL a partir do working-tree (modo do cron)."""
    run_id = os.environ.get("GITHUB_RUN_ID") or f"local-{datetime.now(BRT).strftime('%Y%m%d-%H%M')}"
    run_dt = datetime.now(BRT)
    commit = {"sundek": os.environ.get("GITHUB_SHA"), "ville": os.environ.get("GITHUB_SHA")}

    snap = _montar_snapshot(
        run_id, "deploy", run_dt,
        _read_working(SUNDEK_CLASSIF), _read_working(VILLE_CLASSIF),
        _read_working(SUNDEK_CUSTO), _read_working(VILLE_CUSTO),
        commit,
    )
    if not snap["marcas"]:
        print("history: nada a snapshotar (sem itens Sundek nem Ville) — abortando sem erro.")
        return
    _escrever_snapshot(snap)

    resumos = [r for r in _index_atual() if r.get("run_id") != run_id]
    resumos.append(_resumo_index(snap))
    index = _reescrever_index(resumos, max_runs)
    _prune_orfaos({r["run_id"] for r in index})
    n_prod = _build_produtos()

    t = snap["metricas"]["total"]
    print(f"history OK -> rodada {run_id} ({', '.join(snap['marcas'])}): "
          f"{t['candidatos']} candidatos, {len(snap['produtos'])} produtos no arquivo, "
          f"${t['custo_usd']:.4f}. Index com {len(index)} rodadas. "
          f"Busca global: {n_prod} produtos.")


def backfill(n: int, clean: bool, max_runs: int | None = None) -> None:
    """Reconstrói as últimas n rodadas varrendo o histórico do git (rodar local).

    O teto do index vira max(MAX_RUNS_INDEX, n) por padrão pra NÃO truncar um backfill
    grande — pode sobrescrever com --max-runs.
    """
    cap = max_runs if max_runs is not None else max(MAX_RUNS_INDEX, n)
    if clean and OUT_DIR.exists():
        for f in OUT_DIR.glob("*.json"):
            f.unlink()

    commits_s = _commits(SUNDEK_CLASSIF, n)
    commits_v = _commits(VILLE_CLASSIF, n * 2)  # folga pra parear por tempo
    if not commits_s:
        print("history/backfill: sem commits de coleta-classificada.json no git.")
        return

    resumos: list[dict] = []
    ids: list[str] = []
    for sha_s, dt_s in commits_s:
        # Pareia a Ville pelo commit mais próximo no tempo (± 90 min).
        sha_v, dt_v = None, None
        melhor = timedelta(minutes=90)
        for cv, dv in commits_v:
            delta = abs(dv - dt_s)
            if delta <= melhor:
                melhor = delta
                sha_v, dt_v = cv, dv

        sundek_itens = _show_json(sha_s, SUNDEK_CLASSIF)
        custo_s = _show_json(sha_s, SUNDEK_CUSTO)
        ville_itens = _show_json(sha_v, VILLE_CLASSIF) if sha_v else None
        custo_v = _show_json(sha_v, VILLE_CUSTO) if sha_v else None

        run_id = sha_s[:9]
        snap = _montar_snapshot(
            run_id, "backfill", dt_s,
            sundek_itens, ville_itens, custo_s, custo_v,
            {"sundek": sha_s, "ville": sha_v},
        )
        if not snap["marcas"]:
            continue
        _escrever_snapshot(snap)
        resumos.append(_resumo_index(snap))
        ids.append(run_id)
        t = snap["metricas"]["total"]
        print(f"  {dt_s.strftime('%d/%m %H:%M')}  {run_id}  "
              f"{t['candidatos']} cand · {t['descartados']} desc · ${t['custo_usd']:.4f}")

    index = _reescrever_index(resumos, cap)
    _prune_orfaos({r["run_id"] for r in index})
    n_prod = _build_produtos()
    print(f"\nhistory/backfill OK -> {len(index)} rodadas em {OUT_DIR}")
    print(f"busca global -> {n_prod} produtos em produtos.json")


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o histórico de rodadas (/history).")
    ap.add_argument("--backfill", nargs="?", type=int, const=25, default=None,
                    metavar="N", help="reconstrói as últimas N rodadas do git (default 25; use um número alto, ex. 500, pra pegar todas)")
    ap.add_argument("--clean", action="store_true", help="limpa a pasta history antes (só com --backfill)")
    ap.add_argument("--max-runs", type=int, default=None,
                    metavar="N", help="teto de rodadas no index (default 200)")
    args = ap.parse_args()

    if args.backfill is not None:
        backfill(args.backfill, args.clean, args.max_runs)
    else:
        snapshot(args.max_runs if args.max_runs is not None else MAX_RUNS_INDEX)


if __name__ == "__main__":
    main()
