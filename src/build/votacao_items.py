"""Gera votacao/public/items.json — SÓ compráveis + barganha, pra página de votação.

Junta as duas frentes (Sundek + Vilebrequin). A pessoa vota gostei / não gostei /
discordo em cada candidato. Lê data/coleta-classificada.json (Sundek) e
data/coleta-ville-classificada.json (Ville), filtra decisão in (compravel, medio),
e exporta os campos que o front usa, com os "destaques" (por que virou candidato).
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import APP_DESDE, APP_TAMBEM_IDS, VILLE_ATIVA

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "votacao" / "public" / "items.json"
# Horário da última montagem da lista ("Atualizado às HH:MM" no app; o app consulta a cada minuto).
STATUS = ROOT / "votacao" / "public" / "status.json"

_MIN_POR = {"segundo": 0, "minuto": 1, "hora": 60, "dia": 1440, "semana": 10080, "mes": 43200, "año": 525600}


def _publicado_em(it: dict) -> str | None:
    """Quando o anúncio foi publicado no Vinted, estimado pelo "hace 2 horas" que a página
    mostrava na coleta (campo `upload`, relativo a `coletado_em`)."""
    up = (it.get("upload") or "").strip().lower()
    try:
        base = datetime.fromisoformat(it.get("coletado_em") or "")
    except ValueError:
        return None
    if up in ("ahora mismo", "justo ahora"):
        return base.isoformat()
    m = re.match(r"hace\s+(un|una|unos|unas|\d+)\s+(segundo|minuto|hora|d[ií]a|semana|mes|año)", up)
    if not m:
        return None
    n = 1 if m.group(1) in ("un", "una", "unos", "unas") else int(m.group(1))
    return (base - timedelta(minutes=n * _MIN_POR[m.group(2).replace("í", "i")])).isoformat()


def _num(txt) -> float | None:
    """"10,00 €" / "desde 4,40 €" → 10.0 / 4.4."""
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", str(txt or "").replace("\xa0", " "))
    return float(m.group(1).replace(",", ".")) if m else None


def _e_ville(it: dict) -> bool:
    """Item da Vilebrequin tem etapa de tartaruga/autenticidade própria."""
    return isinstance(it.get("tartaruga"), dict) or isinstance(it.get("autenticidade"), dict)


def _destaques(it: dict) -> list[str]:
    """Atributos positivos que fazem o item ser candidato (pra mostrar no card)."""
    cl = it.get("classificacao") or {}
    cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
    et = it.get("etiqueta") or {}
    d = []

    if _e_ville(it):
        tart = it.get("tartaruga") if isinstance(it.get("tartaruga"), dict) else {}
        auth = it.get("autenticidade") if isinstance(it.get("autenticidade"), dict) else {}
        tipo = cl.get("tipo")
        if tipo == "tartaruga_grande":
            d.append("tartaruga grande" + (f" ({tart.get('tartaruga_variedade')})" if tart.get("tartaruga_variedade") else ""))
        elif tipo == "tartaruga_pequena":
            d.append("tartaruga pequena")
        elif tipo == "liso":
            d.append("liso")
        cor_nome = cor.get("cor_principal") or tart.get("cor_principal")
        bucket = (it.get("score") or {}).get("breakdown", {}).get("cor_bucket")
        if cor_nome and bucket in ("preferida", "neutra"):
            d.append(f"cor {cor_nome} ({bucket})")
        elif cor_nome:
            d.append(f"cor {cor_nome}")
        if (auth.get("autenticidade") or cl.get("autenticidade")) == "original":
            d.append("autêntico (bolso)")
        if et.get("tem_etiqueta") is True:
            d.append("etiqueta")
        return d

    # ---- Sundek (comportamento original) ----
    tier = cor.get("tier_final") or cor.get("tier")
    el = it.get("elastico") or {}
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


# Labels por chave de breakdown (cobre Sundek e Ville).
_PTS_LABEL = {"tier": "cor", "padrao": "padrão", "tamanho": "tam", "elastico": "elástico",
              "etiqueta": "etiqueta", "condicao": "condição", "listra_bonus": "listra",
              "autenticidade": "autent.", "cor": "cor", "fundo": "fundo", "preco": "preço"}
# Ordem de exibição (chaves ausentes são ignoradas).
_ORDEM = ("tier", "padrao", "cor", "fundo", "tamanho", "elastico", "etiqueta",
          "autenticidade", "condicao", "listra_bonus", "preco")


def _por_que(it: dict) -> str:
    """Frase de como o score foi formado."""
    s = it.get("score") or {}
    bd = s.get("breakdown") or {}
    partes = []
    for k in _ORDEM:
        if k in bd and isinstance(bd[k], (int, float)):
            v = bd[k]
            partes.append(f"{_PTS_LABEL.get(k, k)} {'+' if v >= 0 else ''}{v}")
    linha = " · ".join(partes)
    teto = s.get("teto")
    return f"score {s.get('score', 0)}" + (f" (teto €{teto})" if teto else "") + (f": {linha}" if linha else "")


def _recente(it: dict) -> bool:
    """Anúncio do e-mail de 21/10 ou visto pela 1ª vez depois dele (config.APP_DESDE)."""
    if str(it.get("id") or "") in APP_TAMBEM_IDS:
        return True
    datas = [d for d in (it.get("primeiro_visto"), it.get("coletado_em")) if d]
    return bool(datas) and min(datas) >= APP_DESDE


def _carregar(path: Path, marca: str) -> list[dict]:
    if not path.exists():
        return []
    itens = json.loads(path.read_text(encoding="utf-8"))
    cand = []
    for it in itens:
        s = it.get("score") or {}
        if s.get("decisao") not in ("compravel", "medio"):
            continue
        if it.get("status") in ("vendido", "inativo", "removido"):
            continue
        if marca == "sundek" and not _recente(it):
            continue
        cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
        cl = it.get("classificacao") or {}
        el = it.get("elastico") or {}
        auth = it.get("autenticidade") if isinstance(it.get("autenticidade"), dict) else {}
        tart = it.get("tartaruga") if isinstance(it.get("tartaruga"), dict) else {}
        evid = {
            "listra": cl.get("listra_evidencia"),
            "bolso": cl.get("bolso_evidencia") or auth.get("evidencia"),
            "elastico": el.get("evidencia"),
        }
        cand.append({
            "id": str(it.get("id") or ""),
            "marca": marca,
            "url": it.get("url") or "",
            "titulo": it.get("titulo") or "",
            "tamanho": it.get("tamanho") or "?",
            "estado": it.get("estado") or "",
            "preco": it.get("preco") or "",
            "preco_total": it.get("preco_total") or it.get("preco") or "",
            "fotos": (it.get("fotos") or [])[:6],
            "cor_ia": cor.get("cor_principal") or tart.get("cor_principal") or "",
            "tier_ia": cor.get("tier_final") or cor.get("tier") or cl.get("tipo") or "",
            "decisao": s.get("decisao"),
            "score": s.get("score", 0),
            "teto": s.get("teto"),
            "flags": s.get("flags") or [],
            "destaques": _destaques(it),
            "por_que": _por_que(it),
            "evidencias": {k: v for k, v in evid.items() if v},
            "negociacao": s.get("negociacao") or {},
            # Preço em partes (card e e-mail mostram base + taxa + frete; a oferta é sobre o base)
            "preco_base": _num(it.get("preco")),
            "taxa": (round(_num(it.get("preco_total")) - _num(it.get("preco")), 2)
                     if _num(it.get("preco_total")) and _num(it.get("preco"))
                     and _num(it.get("preco_total")) >= _num(it.get("preco")) else None),
            "frete": _num(it.get("envio")),
            # Selo NOVO / "no ar há X" / ordenar por mais recentes
            "primeiro_visto": it.get("primeiro_visto") or it.get("coletado_em"),
            "publicado_em": _publicado_em(it),
        })
    return cand


def main() -> None:
    # --so-ville: gera items.json apenas com a Vilebrequin (usado no deploy do Vercel
    # quando só o feedback da Ville interessa). Default mantém Sundek + Ville.
    parser = argparse.ArgumentParser()
    parser.add_argument("--so-ville", action="store_true", help="exporta apenas itens da Vilebrequin")
    args = parser.parse_args()

    cand = []
    if not args.so_ville:
        cand += _carregar(DATA / "coleta-classificada.json", "sundek")
    if VILLE_ATIVA or args.so_ville:
        cand += _carregar(DATA / "coleta-ville-classificada.json", "vilebrequin")
    # comprável primeiro, depois por score desc
    cand.sort(key=lambda x: (0 if x["decisao"] == "compravel" else 1, -x["score"]))
    OUT.write_text(json.dumps(cand, indent=2, ensure_ascii=False), encoding="utf-8")
    STATUS.write_text(json.dumps({
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(cand),
        "compraveis": sum(1 for x in cand if x["decisao"] == "compravel"),
        "barganhas": sum(1 for x in cand if x["decisao"] == "medio"),
    }, ensure_ascii=False), encoding="utf-8")
    n_comp = sum(1 for x in cand if x["decisao"] == "compravel")
    n_ville = sum(1 for x in cand if x["marca"] == "vilebrequin")
    print(f"OK -> {OUT}  ({len(cand)} candidatos: {n_comp} compráveis, {len(cand) - n_comp} barganha; {n_ville} Ville)")


if __name__ == "__main__":
    main()
