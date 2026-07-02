"""Promove a ÚLTIMA versão de um dataset a BASELINE e limpa as versões antigas.

Use quando gostou de uma versão e quer que ela vire a nova referência — assim as
próximas rodadas passam a comparar contra ela, e a pasta não acumula lixo.

Uso:
  python -m src.gabarito.gabarito_promote --dataset ville
  python -m src.gabarito.gabarito_promote --dataset compraveis_ville
"""
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .gabarito_run import _arg, REG, _versoes, _carregar_rodada


def main() -> None:
    dataset = _arg("--dataset", "ville")
    vs = _versoes(dataset)
    if not vs:
        print(f"Nenhuma versão '{dataset}-vN' pra promover — o baseline já é o mais recente.")
        return

    ultima = vs[-1][1]
    doc = _carregar_rodada(ultima)
    doc["label"] = f"{dataset}-baseline"
    (REG / f"rodada-{dataset}-baseline.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"✓ '{ultima}' virou o novo '{dataset}-baseline' ({len(doc.get('itens', {}))} itens).")

    # Limpa as versões e os comparativos/avals daquele dataset.
    for _, lbl in vs:
        p = REG / f"rodada-{lbl}.json"
        if p.exists():
            p.unlink()
            print("  del", p.name)
    for f in (glob.glob(str(REG / f"comparativo_{dataset}-*.html"))
              + glob.glob(str(REG / f"aval-{dataset}-*.html"))):
        os.remove(f)
        print("  del", os.path.basename(f))

    print(f"Pronto. O próximo `gabarito_run --dataset {dataset}` começa em {dataset}-v1.")


if __name__ == "__main__":
    main()
