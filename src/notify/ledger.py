"""Registro de ofertas já notificadas — evita avisar o mesmo anúncio duas vezes.

data/notificados.json:
{
  "<item_id>": {
    "notificado_em": "<iso>",
    "marca":         "sundek" | "vilebrequin",
    "decisao":       "compravel" | "medio",
    "preco":         "64,00 €"
  }
}
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = ROOT / "data" / "notificados.json"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def carregar() -> dict:
    if not LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        # Ledger corrompido não pode derrubar a rodada — começa vazio.
        return {}


def salvar(ledger: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


def ja_viu_marca(ledger: dict, marca: str | None) -> bool:
    """True se já há ao menos uma entrada dessa marca (controla o seed por marca)."""
    if marca is None:
        return bool(ledger)
    return any(v.get("marca") == marca for v in ledger.values())


def registrar(ledger: dict, itens: list[dict], marca: str | None = None) -> None:
    """Marca os itens como já notificados (sobrescreve a entrada se já existir)."""
    agora = _agora()
    for it in itens:
        id_ = str(it.get("id") or "")
        if not id_:
            continue
        ledger[id_] = {
            "notificado_em": agora,
            "marca": it.get("marca") or marca,
            "decisao": it.get("decisao"),
            "preco": it.get("preco"),
        }


def podar(ledger: dict, dias: int = 30) -> int:
    """Remove entradas mais velhas que `dias` pro ledger não crescer pra sempre.
    Retorna quantas foram removidas."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    removidas = 0
    for id_ in list(ledger):
        try:
            quando = datetime.fromisoformat(ledger[id_]["notificado_em"])
            if quando < limite:
                del ledger[id_]
                removidas += 1
        except Exception:
            continue
    return removidas
