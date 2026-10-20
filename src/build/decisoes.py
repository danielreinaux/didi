"""Gera votacao/public/decisoes.json — página /decisoes (decisões do cliente).

Lê a especificação das perguntas em src/build/decisoes_spec.json (seções →
perguntas, com opções e os ids dos itens de exemplo) e resolve as FOTOS de cada id:

- ids do gabarito (cs*, cv* e os ids de gabarito_sundek.json / gabarito_ville.json):
  fotos locais /gabarito_fotos/<id>/<arquivo> (lista o diretório em
  votacao/public/gabarito_fotos/<id>/); título/url/preço vêm do json do gabarito.
- demais ids: data/coleta-classificada.json → até 4 fotos (URLs do Vinted) + url +
  título + preço. Uma pergunta pode pedir mais com "max_fotos" no spec (ex.: a da
  etiqueta M520, em que a foto da etiqueta/botão é a 5ª do anúncio).
- id não encontrado (ou sem foto) → erro. Nada é emitido em silêncio.

Também grava no topo um bloco "resumo" (antes × depois dos ajustes da IA Sundek),
com os números já medidos — ver RESUMO abaixo.

Os votos NÃO passam por aqui: a página grava em /api/reactions com a chave
"decisao:<id_da_pergunta>" (reaction = texto da opção, observacao = comentário).

Uso:  python -m src.build.decisoes
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SPEC = Path(__file__).resolve().parent / "decisoes_spec.json"
PUBLIC = ROOT / "votacao" / "public"
FOTOS_DIR = PUBLIC / "gabarito_fotos"
COLETA = ROOT / "data" / "coleta-classificada.json"
OUT = PUBLIC / "decisoes.json"

# jsons do gabarito servidos pelo app (título/url/preço dos itens com foto local).
GABARITOS = (
    "gabarito_sundek.json",
    "gabarito_ville.json",
    "gabarito_compraveis_sundek.json",
    "gabarito_compraveis_ville.json",
)
MAX_FOTOS_COLETA = 4
EXT_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
STATUS_VALIDOS = {"ja_aplicado", "pendente"}

# Antes × depois dos ajustes da IA Sundek (medido contra o gabarito; números
# fornecidos prontos — não são recalculados aqui).
RESUMO = {
    "titulo": "O que mudou com os ajustes",
    "destaques": [
        {"rotulo": "Compráveis bons descartados por engano", "antes": "12 de 40", "depois": "1 de 40"},
        {"rotulo": "Decisão igual à humana — gabarito Sundek", "antes": "94%", "depois": "98%"},
        {"rotulo": "Decisão igual à humana — compráveis", "antes": "70%", "depois": "93%"},
        {"rotulo": "Ruins que passaram (gabarito Sundek)", "antes": "1", "depois": "0"},
    ],
}


class SpecErro(Exception):
    pass


def _ordem_foto(nome: str):
    """0.jpeg, 1.jpeg, …, 10.jpeg em ordem numérica (não lexicográfica)."""
    m = re.match(r"(\d+)", nome)
    return (0, int(m.group(1)), nome) if m else (1, 0, nome)


def _fotos_locais(item_id: str) -> list[str]:
    d = FOTOS_DIR / item_id
    if not d.is_dir():
        return []
    arqs = sorted(
        (p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXT_FOTO),
        key=_ordem_foto,
    )
    return [f"/gabarito_fotos/{item_id}/{a}" for a in arqs]


def _carrega_gabaritos() -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for nome in GABARITOS:
        p = PUBLIC / nome
        if not p.exists():
            raise SpecErro(f"arquivo do gabarito não encontrado: {p}")
        for it in json.loads(p.read_text(encoding="utf-8")).get("itens", []):
            idx.setdefault(str(it["id"]), it)
    return idx


def _carrega_coleta(ids: set[str]) -> dict[str, dict]:
    """Só os ids pedidos. Se o id aparecer mais de uma vez, fica a coleta mais recente com foto."""
    if not COLETA.exists():
        raise SpecErro(f"{COLETA} não encontrado")
    out: dict[str, dict] = {}
    for it in json.loads(COLETA.read_text(encoding="utf-8")):
        i = str(it.get("id"))
        if i not in ids or not it.get("fotos"):
            continue
        atual = out.get(i)
        if atual is None or (it.get("coletado_em") or "") > (atual.get("coletado_em") or ""):
            out[i] = it
    return out


def _e_gabarito(item_id: str, gab: dict[str, dict]) -> bool:
    return item_id.startswith(("cs", "cv")) or item_id in gab


def _ids_da_pergunta(p: dict) -> list[str]:
    if "itens" in p:
        return [str(x["id"]) for x in p["itens"]]
    return [str(i) for g in p["grupos"] for i in g["itens"]]


def _valida_spec(spec: dict) -> None:
    vistos: set[str] = set()
    for s in spec.get("secoes") or []:
        for campo in ("id", "titulo", "perguntas"):
            if not s.get(campo):
                raise SpecErro(f"seção sem '{campo}': {s.get('id')!r}")
        for p in s["perguntas"]:
            pid = p.get("id")
            if not pid or not re.fullmatch(r"[a-z0-9_]+", pid):
                raise SpecErro(f"pergunta com id inválido: {pid!r}")
            if pid in vistos:
                raise SpecErro(f"id de pergunta repetido: {pid}")
            vistos.add(pid)
            if not p.get("titulo"):
                raise SpecErro(f"{pid}: sem título")
            ops = p.get("opcoes") or []
            if not ops or len(set(ops)) != len(ops):
                raise SpecErro(f"{pid}: opções vazias ou repetidas")
            if ("itens" in p) == ("grupos" in p):
                raise SpecErro(f"{pid}: precisa ter OU 'itens' OU 'grupos'")
            if "grupos" in p and any(not g.get("rotulo") or not g.get("itens") for g in p["grupos"]):
                raise SpecErro(f"{pid}: grupo sem rótulo ou sem itens")
            if "itens" in p and not p["itens"]:
                raise SpecErro(f"{pid}: lista de itens vazia")
            mf = p.get("max_fotos")
            if mf is not None and (not isinstance(mf, int) or isinstance(mf, bool) or mf < 1):
                raise SpecErro(f"{pid}: max_fotos deve ser inteiro >= 1 (achei {mf!r})")
            st = p.get("status")
            if s["id"] == "regras" and st not in STATUS_VALIDOS:
                raise SpecErro(f"{pid}: status deve ser um de {sorted(STATUS_VALIDOS)} (achei {st!r})")
            if st is not None and st not in STATUS_VALIDOS:
                raise SpecErro(f"{pid}: status inválido {st!r}")
    if not vistos:
        raise SpecErro("spec sem perguntas")


def build(spec: dict) -> dict:
    _valida_spec(spec)
    gab = _carrega_gabaritos()

    todos = {i for s in spec["secoes"] for p in s["perguntas"] for i in _ids_da_pergunta(p)}
    coleta = _carrega_coleta({i for i in todos if not _e_gabarito(i, gab)})

    cache: dict[tuple[str, int], dict] = {}
    faltando: list[str] = []

    def resolve(item_id: str, max_fotos: int) -> dict | None:
        if (item_id, max_fotos) in cache:
            return cache[(item_id, max_fotos)]
        if _e_gabarito(item_id, gab):
            fotos = _fotos_locais(item_id)
            g = gab.get(item_id) or {}
            if not fotos:
                faltando.append(f"{item_id} (gabarito, sem fotos em {FOTOS_DIR / item_id})")
                return None
            r = {
                "id": item_id,
                "origem": "gabarito",
                "titulo": g.get("titulo"),
                "url": g.get("url"),
                "preco": g.get("preco"),
                "fotos": fotos,
            }
        else:
            c = coleta.get(item_id)
            if not c:
                faltando.append(f"{item_id} (não está em {COLETA.name} ou está sem fotos)")
                return None
            r = {
                "id": item_id,
                "origem": "coleta",
                "titulo": c.get("titulo"),
                "url": c.get("url"),
                "preco": c.get("preco"),
                "fotos": list(c["fotos"][:max_fotos]),
            }
        cache[(item_id, max_fotos)] = r
        return r

    def item_saida(item_id: str, legenda: str | None = None, max_fotos: int = MAX_FOTOS_COLETA) -> dict:
        base = resolve(item_id, max_fotos) or {"id": item_id}
        out = dict(base)
        if legenda:
            out["legenda"] = legenda
        return out

    secoes = []
    total = 0
    for s in spec["secoes"]:
        perguntas = []
        for p in s["perguntas"]:
            q = {"id": p["id"], "titulo": p["titulo"]}
            if p.get("contexto"):
                q["contexto"] = p["contexto"]
            if p.get("status"):
                q["status"] = p["status"]
            q["opcoes"] = list(p["opcoes"])
            mf = p.get("max_fotos") or MAX_FOTOS_COLETA
            if "itens" in p:
                q["itens"] = [item_saida(str(x["id"]), x.get("legenda"), mf) for x in p["itens"]]
            else:
                q["grupos"] = [
                    {"rotulo": g["rotulo"], "itens": [item_saida(str(i), None, mf) for i in g["itens"]]}
                    for g in p["grupos"]
                ]
            perguntas.append(q)
            total += 1
        sec = {"id": s["id"], "titulo": s["titulo"]}
        if s.get("intro"):
            sec["intro"] = s["intro"]
        sec["perguntas"] = perguntas
        secoes.append(sec)

    if faltando:
        raise SpecErro("ids sem foto/dados:\n  - " + "\n  - ".join(dict.fromkeys(faltando)))

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": "src/build/decisoes_spec.json",
        "chave_voto": "decisao:<id_da_pergunta>",
        "titulo": spec.get("titulo") or "Decisões",
        "intro": spec.get("intro") or "",
        "resumo": RESUMO,
        "total_perguntas": total,
        "secoes": secoes,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, default=SPEC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    try:
        doc = build(json.loads(a.spec.read_text(encoding="utf-8")))
    except SpecErro as e:
        print(f"ERRO decisoes: {e}", file=sys.stderr)
        return 1
    a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_itens = sum(
        len(p.get("itens") or [i for g in p.get("grupos", []) for i in g["itens"]])
        for s in doc["secoes"]
        for p in s["perguntas"]
    )
    print(f"decisoes.json: {doc['total_perguntas']} perguntas, {n_itens} itens → {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
