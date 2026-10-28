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


def _ja_avisado(it: dict, ledger: dict) -> bool:
    """Já está no ledger E nada de novo aconteceu: um anúncio avisado como oferta comum que
    depois virou short premiado (ou um premiado que baixou o preço pra "compra urgente") é
    avisado de novo — é o alerta que o cliente pediu."""
    e = ledger.get(str(it.get("id") or ""))
    if not e:
        return False
    p = it.get("premiado") or {}
    if p.get("modelo") and not e.get("premiado"):
        return False
    if p.get("urgente") and not e.get("urgente"):
        return False
    return True


def _ordem_premiado(it: dict) -> int:
    p = it.get("premiado") or {}
    return 0 if p.get("urgente") else (1 if p.get("modelo") else 2)


def novos(itens: list[dict], ledger: dict) -> list[dict]:
    """Candidatos ainda não notificados, ordenados: premiado urgente → premiado → urgente →
    comprável → barganha, e por score desc dentro de cada grupo."""
    out = [it for it in itens if not _ja_avisado(it, ledger)]
    out.sort(key=lambda x: (
        _ordem_premiado(x),
        0 if _urgente(x) else 1,
        0 if x.get("decisao") == "compravel" else 1,
        -(x.get("score") or 0),
    ))
    return out
