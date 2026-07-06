"""Audita (e opcionalmente faz backfill) do fingerprint _dc_fotos do double-check.

O double-check com gpt-4o só reprocessa itens "ambíguos". Um item já conferido
deixa de ser ambíguo quando tem `_model=gpt-4o` E `_dc_fotos` batendo com as fotos
atuais. Este script:

  python verifica_dc.py            → só audita: quantos ainda iriam pro gpt-4o
  python verifica_dc.py --aplicar  → carimba _dc_fotos (grátis, sem API) nos já
                                      conferidos que ainda não têm o campo, e salva

Backfillar aqui é seguro/grátis porque o fingerprint é só um hash das fotos que já
estão no item — não re-classifica nada. Só carimba quem já tem _model=gpt-4o e
nenhum _dc_fotos (nunca sobrescreve um fingerprint que não bate: fotos diferentes
significam que o item mudou e DEVE ser re-conferido).

⚠️ Mantém _is_ambiguo/_fotos_fingerprint em sincronia com src/classify/reclassify_ambiguos.py
"""
import hashlib
import json
import sys
from pathlib import Path

# Console do Windows (cp1252) quebra em setas/emoji — força UTF-8 na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "data" / "coleta-classificada.json"
MODEL_FORTE = "gpt-4o"


def _fotos_fingerprint(item: dict) -> str:
    fotos = item.get("fotos") or []
    return hashlib.md5("|".join(fotos).encode("utf-8")).hexdigest()[:12]


def _is_ambiguo(item: dict) -> bool:
    cl = item.get("classificacao") or {}
    if cl.get("tipo") != "liso":
        return False
    if cl.get("_model") == MODEL_FORTE and cl.get("_dc_fotos") == _fotos_fingerprint(item):
        return False
    bicolor = cl.get("bicolor", False)
    brilhoso = cl.get("tecido_brilhoso", False)
    listra = cl.get("tem_listra_lateral_sundek", False)
    listra_frente = cl.get("listra_na_frente", False)
    score_decisao = (item.get("score") or {}).get("decisao", "")
    if not listra and not bicolor:
        return True
    if listra_frente:
        return True
    if score_decisao == "compravel" and not brilhoso and not bicolor:
        return True
    return False


def main() -> None:
    aplicar = "--aplicar" in sys.argv[1:]
    todos = json.loads(PATH.read_text(encoding="utf-8"))

    ja_4o = [it for it in todos if (it.get("classificacao") or {}).get("_model") == MODEL_FORTE]
    com_fp = [it for it in ja_4o if (it.get("classificacao") or {}).get("_dc_fotos")]
    ambiguos = [it for it in todos if _is_ambiguo(it)]
    # dos ambíguos, quais já são gpt-4o (backfill pendente) vs nunca conferidos (novos)
    amb_backfill = [it for it in ambiguos if (it.get("classificacao") or {}).get("_model") == MODEL_FORTE]
    amb_novos = len(ambiguos) - len(amb_backfill)

    print(f"Acervo total ................... {len(todos)}")
    print(f"Já conferidos com gpt-4o ....... {len(ja_4o)}")
    print(f"  destes, com _dc_fotos gravado  {len(com_fp)}")
    print(f"Iriam pro gpt-4o na próxima run  {len(ambiguos)}")
    print(f"  - já conferidos (backfill) ... {len(amb_backfill)}  ← evitáveis de graça")
    print(f"  - novos/foto mudou ........... {amb_novos}  ← re-conferir é correto")

    if not aplicar:
        if amb_backfill:
            print(f"\nRode  python verifica_dc.py --aplicar  pra carimbar os "
                  f"{len(amb_backfill)} sem gastar gpt-4o.")
        else:
            print("\n✅ Nenhum backfill pendente — a próxima run não re-cobra os antigos.")
        return

    # --aplicar: carimba fingerprint só nos gpt-4o que ainda não têm _dc_fotos
    carimbados = 0
    for it in todos:
        cl = it.get("classificacao") or {}
        if cl.get("_model") == MODEL_FORTE and not cl.get("_dc_fotos"):
            cl["_dc_fotos"] = _fotos_fingerprint(it)
            carimbados += 1

    PATH.write_text(json.dumps(todos, indent=2, ensure_ascii=False), encoding="utf-8")
    restam = [it for it in todos if _is_ambiguo(it)]
    print(f"\n✅ {carimbados} itens carimbados (grátis, sem API). Salvo em {PATH.name}.")
    print(f"   Agora iriam pro gpt-4o na próxima run: {len(restam)} (só novos/foto mudada).")


if __name__ == "__main__":
    main()
