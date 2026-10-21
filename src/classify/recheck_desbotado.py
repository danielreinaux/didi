"""ONE-OFF: reprocessa (pipeline Sundek inteiro, já com o 2º olhar do desbotado) os lisos
ATIVOS que o pipeline antigo descartou como "desbotado". Hoje: ~68 itens; os que deixarem
de ser desbotado rodam cor/listra/elástico/bolso/etiqueta → custo one-off ~US$1–2.

  python -m src.classify.recheck_desbotado --dry   # só conta
  python -m src.classify.recheck_desbotado         # reprocessa e grava no acervo
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .run import _processar
from .score import calcular_score

PATH = Path(__file__).resolve().parent.parent.parent / "data" / "coleta-classificada.json"


def _alvo(it: dict) -> bool:
    cl = it.get("classificacao") or {}
    return (it.get("status") == "ativo" and cl.get("tipo") == "desbotado"
            and cl.get("tipo_original") in ("liso", "indefinido", None)
            and not cl.get("desbotado_check") and not it.get("manual_exclusao"))


def main() -> None:
    todos = json.loads(PATH.read_text())
    idx = [i for i, it in enumerate(todos) if _alvo(it)]
    print(f"lisos ativos descartados por desbotado (sem 2º olhar): {len(idx)}")
    if "--dry" in sys.argv:
        return

    def tarefa(i):
        novo, _, _ = _processar(todos[i], str(i), len(todos))
        novo["score"] = calcular_score(novo)
        return i, novo

    mudou = 0
    with ThreadPoolExecutor(2) as ex:
        for i, novo in ex.map(tarefa, idx):
            antes = (todos[i].get("score") or {}).get("decisao")
            todos[i] = novo
            if (novo.get("classificacao") or {}).get("tipo") != "desbotado":
                mudou += 1
                print(f"  {novo.get('id')}: desbotado → {(novo['classificacao']).get('tipo')} · {antes} → {novo['score'].get('decisao')}")
    PATH.write_text(json.dumps(todos, indent=2, ensure_ascii=False))
    print(f"{mudou}/{len(idx)} deixaram de ser desbotado.")


if __name__ == "__main__":
    main()
