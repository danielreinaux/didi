"""Histórico longitudinal de itens. Persiste preço por data e detecta vendidos.

Estrutura em data/historico.json:
{
  "<item_id>": {
    "primeiro_visto": "<iso>",
    "ultimo_visto":   "<iso>",
    "scrapes_visto":  <int>,
    "vendido":        bool,
    "vendido_em":     "<iso>" | null,
    "titulo_atual":   "<str>",
    "url":            "<str>",
    "snapshots":      [
       {"data": "<iso>", "preco": "10,00 €", "titulo": "..."},
       ...
    ]
  }
}
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HISTORICO_PATH = ROOT / "data" / "historico.json"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _carregar() -> dict:
    if not HISTORICO_PATH.exists():
        return {}
    try:
        return json.loads(HISTORICO_PATH.read_text())
    except Exception:
        return {}


def _salvar(historico: dict) -> None:
    HISTORICO_PATH.write_text(json.dumps(historico, indent=2, ensure_ascii=False))


def atualizar_com_scrape(itens_scrape: list[dict]) -> dict:
    """Atualiza o histórico com os itens de um scrape recém-feito.

    Retorna stats: {novos, ainda_listados, preco_baixou, vendidos}.
    """
    historico = _carregar()
    agora = _agora()
    ids_novos = {it.get("id") for it in itens_scrape if it.get("id")}

    novos = 0
    ainda = 0
    baixou = 0

    for it in itens_scrape:
        id_ = it.get("id")
        if not id_:
            continue
        preco = it.get("preco") or ""
        titulo = it.get("titulo") or ""

        if id_ not in historico:
            historico[id_] = {
                "primeiro_visto": agora,
                "ultimo_visto":   agora,
                "scrapes_visto":  1,
                "vendido":        False,
                "vendido_em":     None,
                "titulo_atual":   titulo,
                "url":            it.get("url"),
                "snapshots":      [{"data": agora, "preco": preco, "titulo": titulo}],
            }
            novos += 1
        else:
            h = historico[id_]
            ultimo_preco = h["snapshots"][-1]["preco"] if h["snapshots"] else None
            h["ultimo_visto"] = agora
            h["scrapes_visto"] = h.get("scrapes_visto", 0) + 1
            h["titulo_atual"] = titulo
            # Reabriu? (estava vendido mas voltou)
            if h.get("vendido"):
                h["vendido"] = False
                h["vendido_em"] = None
            # Snapshot só se preço mudou
            if preco != ultimo_preco:
                h["snapshots"].append({"data": agora, "preco": preco, "titulo": titulo})
                if ultimo_preco and preco and _menor(preco, ultimo_preco):
                    baixou += 1
            ainda += 1

    # Marca vendidos: ids no histórico que NÃO apareceram neste scrape
    # (e que ainda não estavam marcados como vendido)
    vendidos_agora = 0
    for id_, h in historico.items():
        if id_ in ids_novos:
            continue
        if not h.get("vendido"):
            h["vendido"] = True
            h["vendido_em"] = agora
            vendidos_agora += 1

    _salvar(historico)
    return {
        "novos": novos,
        "ainda_listados": ainda,
        "preco_baixou": baixou,
        "vendidos_agora": vendidos_agora,
        "total_historico": len(historico),
    }


def _parse_preco_num(p: str) -> float | None:
    if not p:
        return None
    import re
    m = re.findall(r"[\d,\.]+", p)
    if not m:
        return None
    try:
        return float(m[0].replace(",", "."))
    except Exception:
        return None


def _menor(a: str, b: str) -> bool:
    """True se preço a < preço b."""
    pa = _parse_preco_num(a)
    pb = _parse_preco_num(b)
    if pa is None or pb is None:
        return False
    return pa < pb


def info(item_id: str) -> dict | None:
    h = _carregar()
    return h.get(item_id)
