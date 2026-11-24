"""Registro de ofertas já notificadas — evita avisar o mesmo anúncio duas vezes.

data/notificados.json:
{
  "<item_id>": {
    "notificado_em": "<iso>",
    "marca":         "sundek" | "vilebrequin",
    "decisao":       "compravel" | "medio",
    "preco":         "64,00 €",
    "premiado":      1 | 2 | 3 | null,   # avisado como short premiado (modelo)
    "urgente":       true | false        # avisado como premiado "compra urgente"
  }
}
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = ROOT / "data" / "notificados.json"
# Ville com e-mail próprio (24/11/2026): o job ville avisa a Ville logo depois da análise dele e
# registra aqui. Cada arquivo tem UM escritor (job sundek → notificados.json; job ville → este),
# então os dois jobs em paralelo não colidem no push. Para não reavisar, o notify lê os dois
# (as entradas antigas da Ville seguem no notificados.json até a poda de 30 dias).
LEDGER_VILLE_PATH = ROOT / "data" / "notificados-ville.json"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def carregar(caminho: Path | None = None) -> dict:
    caminho = caminho or LEDGER_PATH
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        # Ledger corrompido não pode derrubar a rodada — começa vazio.
        return {}


def salvar(ledger: dict, caminho: Path | None = None) -> None:
    caminho = caminho or LEDGER_PATH
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


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
            "premiado": (it.get("premiado") or {}).get("modelo"),
            "urgente": bool((it.get("premiado") or {}).get("urgente")),
        }


def podar(ledger: dict, dias: int = 30, manter: set[str] | None = None) -> int:
    """Remove entradas mais velhas que `dias` pro ledger não crescer pra sempre — MENOS as
    de `manter` (ids ainda na lista do app): esquecer um anúncio que segue à venda fazia o
    e-mail reenviá-lo como "novo" 30 dias depois. Retorna quantas foram removidas."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    manter = manter or set()
    removidas = 0
    for id_ in list(ledger):
        if id_ in manter:
            continue
        try:
            quando = datetime.fromisoformat(ledger[id_]["notificado_em"])
            if quando < limite:
                del ledger[id_]
                removidas += 1
        except Exception:
            continue
    return removidas
