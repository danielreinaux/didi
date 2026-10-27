"""Gravação compacta do acervo (data/coleta-classificada.json) e de outros JSONs grandes.

Por quê (27/10/2026): o acervo tinha 77 MB com indent=2 — perto do limite de 100 MB por arquivo
do GitHub (a partir daí o push das rodadas falha) — e é regravado a cada rodada. 77% dele são
anúncios vendidos/removidos que não mudam mais. Agora:
  - um anúncio por linha, sem espaços (diff do git continua por anúncio);
  - anúncio vendido/removido fica enxuto: só a 1ª foto (os links do Vinted expiram de qualquer
    jeito), sem vendedor/acoes (só o scraper escrevia, ninguém lê);
  - sai de todos os anúncios o raciocínio do prompt antigo do elástico (pensamento_*).
"""
import json
from pathlib import Path

_INATIVOS = ("vendido", "removido", "inativo")


def enxugar(it: dict) -> dict:
    el = it.get("elastico")
    if isinstance(el, dict) and any(k.startswith("pensamento_") for k in el):
        it["elastico"] = {k: v for k, v in el.items() if not k.startswith("pensamento_")}
    if it.get("status") in _INATIVOS:
        it.pop("vendedor", None)
        it.pop("acoes", None)
        if isinstance(it.get("fotos"), list) and len(it["fotos"]) > 1:
            it["fotos"] = it["fotos"][:1]
    return it


def _linha(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def salvar_lista(path: Path, itens: list, enxuga: bool = False) -> None:
    """Lista JSON com um elemento por linha (lida normalmente por json.loads)."""
    if enxuga:
        itens = [enxugar(it) if isinstance(it, dict) else it for it in itens]
    corpo = ",\n".join(_linha(it) for it in itens)
    Path(path).write_text("[\n" + corpo + "\n]\n" if corpo else "[]\n", encoding="utf-8")


def salvar_dict(path: Path, d: dict) -> None:
    """Objeto JSON com uma chave por linha."""
    corpo = ",\n".join(_linha(str(k)) + ":" + _linha(v) for k, v in d.items())
    Path(path).write_text("{\n" + corpo + "\n}\n" if corpo else "{}\n", encoding="utf-8")
