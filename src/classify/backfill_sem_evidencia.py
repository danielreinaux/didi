"""Backfill: aplica a nova regra `sem_evidencia` no JSON já classificado.

Critério (mesmo do pipeline em ville_run.py):
  marca_check.e_vilebrequin == "indefinido" E marca_check.confianca == 0
  → tipo passa a "sem_evidencia" e score é recalculado (vira descartado).

Não chama IA. Roda em cima de data/coleta-ville-classificada.json in-place.

Uso: python -m src.classify.backfill_sem_evidencia
"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .score_ville import calcular_score

ROOT = Path(__file__).resolve().parent.parent.parent
PATH = ROOT / "data" / "coleta-ville-classificada.json"


def deve_reclassificar(item: dict) -> bool:
    cl = item.get("classificacao") or {}
    if cl.get("tipo") == "sem_evidencia":
        return False  # já tá no novo tipo
    marca = item.get("marca_check") or {}
    return (
        marca.get("e_vilebrequin") == "indefinido"
        and (marca.get("confianca") or 0) == 0
    )


def main() -> None:
    if not PATH.exists():
        print(f"Arquivo não encontrado: {PATH}")
        sys.exit(1)

    itens = json.loads(PATH.read_text(encoding="utf-8"))
    alterados = 0
    for item in itens:
        if not deve_reclassificar(item):
            continue
        marca = item.get("marca_check") or {}
        item["classificacao"] = {
            "tipo": "sem_evidencia",
            "motivo": marca.get("evidencia") or "sem evidência visual do produto",
            "confianca": 0,
        }
        item["score"] = calcular_score(item)
        alterados += 1

    PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Backfill concluído: {alterados} itens reclassificados como 'sem_evidencia'.")


if __name__ == "__main__":
    main()
