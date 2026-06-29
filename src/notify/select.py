"""Seleciona, do votacao/public/items.json, os candidatos novos pra notificar.

O items.json já vem filtrado (só compravel/medio, sem vendido/inativo) pelo
build/votacao_items.py — então a condição "Todos" é simplesmente "todo candidato
cujo id ainda não está no ledger".
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ITEMS_PATH = ROOT / "votacao" / "public" / "items.json"


def candidatos(marca: str | None = None) -> list[dict]:
    """Lê o items.json recém-gerado; opcionalmente filtra por marca."""
    if not ITEMS_PATH.exists():
        return []
    try:
        itens = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if marca:
        itens = [it for it in itens if it.get("marca") == marca]
    return itens


def _urgente(it: dict) -> bool:
    return bool((it.get("negociacao") or {}).get("comprar_ja"))


def novos(itens: list[dict], ledger: dict) -> list[dict]:
    """Candidatos ainda não notificados, ordenados: urgente → comprável → barganha,
    e por score desc dentro de cada grupo."""
    out = [it for it in itens if str(it.get("id") or "") not in ledger]
    out.sort(key=lambda x: (
        0 if _urgente(x) else 1,
        0 if x.get("decisao") == "compravel" else 1,
        -(x.get("score") or 0),
    ))
    return out
