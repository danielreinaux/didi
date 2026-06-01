"""Gera votacao/public/items.json — SÓ compráveis + barganha, pra página de votação.

A pessoa vota gostei / não gostei / discordo em cada candidato (não no acervo inteiro).
Lê data/coleta-classificada.json, filtra decisão in (compravel, medio), e exporta os
campos que o front usa, com os "destaques" (por que virou candidato).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "votacao" / "public" / "items.json"


def _destaques(it: dict) -> list[str]:
    """Atributos positivos que fazem o item ser candidato (pra mostrar no card)."""
    cl = it.get("classificacao") or {}
    cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
    el = it.get("elastico") or {}
    et = it.get("etiqueta") or {}
    d = []
    tier = cor.get("tier_final") or cor.get("tier")
    if tier in ("maravilhoso", "muito_boa", "boa"):
        d.append(f"cor {cor.get('cor_principal')} ({tier})")
    if cl.get("tem_listra_lateral_sundek") is True:
        cores = cl.get("cores_listras") or []
        d.append("listra Sundek" + (f" ({', '.join(cores)})" if cores else ""))
    if cl.get("tem_bolso_traseiro") is True and cl.get("bolso_traseiro_tem_nome") is True:
        d.append("bolso + nome")
    if el.get("tem_elastico") is True:
        d.append("elástico")
    if et.get("tem_etiqueta") is True:
        d.append("etiqueta")
    return d


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())
    cand = []
    for it in itens:
        s = it.get("score") or {}
        if s.get("decisao") not in ("compravel", "medio"):
            continue
        if it.get("status") in ("vendido", "inativo"):
            continue
        cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
        cand.append({
            "id": str(it.get("id") or ""),
            "url": it.get("url") or "",
            "titulo": it.get("titulo") or "",
            "tamanho": it.get("tamanho") or "?",
            "estado": it.get("estado") or "",
            "preco": it.get("preco") or "",
            "preco_total": it.get("preco_total") or it.get("preco") or "",
            "fotos": (it.get("fotos") or [])[:6],
            "cor_ia": cor.get("cor_principal") or "",
            "tier_ia": cor.get("tier_final") or cor.get("tier") or "",
            "decisao": s.get("decisao"),
            "score": s.get("score", 0),
            "destaques": _destaques(it),
        })
    # comprável primeiro, depois por score desc
    cand.sort(key=lambda x: (0 if x["decisao"] == "compravel" else 1, -x["score"]))
    OUT.write_text(json.dumps(cand, indent=2, ensure_ascii=False))
    n_comp = sum(1 for x in cand if x["decisao"] == "compravel")
    print(f"OK -> {OUT}  ({len(cand)} candidatos: {n_comp} compráveis, {len(cand) - n_comp} barganha)")


if __name__ == "__main__":
    main()
