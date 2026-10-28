"""Gera votacao/public/descartados.json — a aba "Descartados" do app.

Pedido do cliente (27/10/2026): ver o que a IA está cortando, pra apontar o que devia ter
passado. O /history não serve pra isso: cada rodada lá é a foto do acervo inteiro e só traz os
120 descartados de MAIOR score — os cortados com score 0 (a maioria) nem aparecem.

Aqui: os anúncios Sundek DESCARTADOS vistos pela 1ª vez nas últimas HORAS, mais novos primeiro,
com o motivo em português. "obvio" = não é short / outra marca / infantil / tamanho fora (o app
esconde esses por padrão).
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .votacao_items import _num, _publicado_em

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "votacao" / "public" / "descartados.json"
HORAS = 72

# motivo_exclusao (classify/score.py) → (grupo do filtro, texto pro cliente)
_EXCLUSAO = {
    "nao_short": ("nao_e_short", "não é short de banho"),
    "nao_sundek": ("nao_e_short", "não é Sundek"),
    "infantil": ("nao_e_short", "infantil"),
    "tamanho_invalido": ("tamanho", "tamanho fora (S–XL ou 31–34)"),
    "tamanho_XS": ("tamanho", "tamanho XS"),
    "tamanho_XXL": ("tamanho", "tamanho XXL"),
    "estampado": ("estampa", "estampado"),
    "logo_grande": ("estampa", "logo grande"),
    "desbotado": ("cor", "desbotado"),
    "cor_ruim": ("cor", "cor fraca"),
    "combinacao_listra_cor_ruim": ("cor", "a listra não combina com a cor"),
    "tecido_brilhoso": ("cor", "tecido brilhoso"),
    "bicolor": ("cor", "bicolor"),
    "fechamento_botao": ("detalhe", "fecha com botão"),
    "fechamento_velcro": ("detalhe", "fecha com velcro"),
    "bolso_frontal": ("detalhe", "bolso na frente"),
    "listra_na_frente": ("detalhe", "listra na frente"),
    "sem_bolso_traseiro": ("detalhe", "sem bolso traseiro"),
    "bolso_so_logo_colecao_antiga": ("detalhe", "bolso só com o logo (coleção antiga)"),
    "sem_listra_sundek": ("detalhe", "sem a listra Sundek"),
    "piping_nao_e_listra_sundek": ("detalhe", "friso na costura, não é listra Sundek"),
    "sem_elastico_cor_fraca": ("elastico", "sem elástico (assim só passa preto ou branco)"),
}
# Ordem de prioridade do grupo principal (o filtro do app usa o principal).
_ORDEM_GRUPO = ("nao_e_short", "tamanho", "estampa", "cor", "detalhe", "elastico", "preco", "outro")
OBVIOS = {"nao_e_short", "tamanho"}


def _eur(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 0.005 else f"{v:.2f}".replace(".", ",")


def _motivos(it: dict) -> list[tuple[str, str]]:
    """[(grupo, texto)] na ordem de prioridade."""
    s = it.get("score") or {}
    out = []
    for tok in [t.strip() for t in (s.get("motivo_exclusao") or "").split(",") if t.strip()]:
        if tok in _EXCLUSAO:
            out.append(_EXCLUSAO[tok])
        elif tok.startswith("tamanho_numerico_"):
            out.append(("tamanho", f"tamanho {tok.rsplit('_', 1)[-1]} (fora de 31–34)"))
        elif tok.startswith("fechamento_"):
            out.append(("detalhe", f"fecha com {tok.split('_', 1)[1]}"))
        else:
            out.append(("outro", tok.replace("_", " ")))
    mot = s.get("motivo") or ""
    m = re.match(r"preço €([\d.]+) acima do teto €([\d.]+)", mot)
    if m:
        total, teto = float(m.group(1)), float(m.group(2))
        out.append(("preco", f"caro: €{_eur(total)} com a taxa, o limite era €{_eur(teto * 1.25)}"))
    elif (m := re.match(r"sem elástico, (.+) acima de €(\d+)", mot)):
        out.append(("elastico", f"sem elástico: {m.group(1).lower()} só passa até €{m.group(2)}"))
    elif mot == "score baixo":
        out.append(("preco", f"pontuação baixa ({s.get('score', 0)} de 100)"))
    elif mot and not out:
        out.append(("outro", mot))
    out.sort(key=lambda gm: _ORDEM_GRUPO.index(gm[0]))
    return out


def _item(it: dict) -> dict | None:
    mots = _motivos(it)
    if not mots:
        return None
    grupo = mots[0][0]
    obvio = grupo in OBVIOS
    cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
    cl = it.get("classificacao") or {}
    preco, total = _num(it.get("preco")), _num(it.get("preco_total"))
    return {
        "id": str(it.get("id") or ""),
        "url": it.get("url") or "",
        "titulo": it.get("titulo") or "",
        "tamanho": it.get("tamanho") or "?",
        "estado": it.get("estado") or "",
        "preco_base": preco,
        "taxa": round(total - preco, 2) if preco and total and total >= preco else None,
        "frete": _num(it.get("envio")),
        "fotos": (it.get("fotos") or [])[:5],
        "primeiro_visto": it.get("primeiro_visto") or it.get("coletado_em"),
        "publicado_em": _publicado_em(it),
        "status": it.get("status") or "ativo",
        "score": (it.get("score") or {}).get("score", 0),
        "grupo": grupo,
        "obvio": obvio,
        # Não-short: só o motivo principal (o "sem elástico" de uma camiseta é ruído).
        "motivos": [m for _, m in (mots[:1] if obvio else mots)],
        "cor": cor.get("cor_principal") or "",
        "listras": cl.get("cores_listras") or [],
        "elastico": (it.get("elastico") or {}).get("tem_elastico"),
    }


def main(horas: int = HORAS) -> None:
    path = DATA / "coleta-classificada.json"
    if not path.exists():
        return
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    itens = []
    for it in json.loads(path.read_text(encoding="utf-8")):
        if (it.get("score") or {}).get("decisao") != "descartado":
            continue
        if (it.get("primeiro_visto") or it.get("coletado_em") or "") < desde:
            continue
        d = _item(it)
        if d:
            itens.append(d)
    itens.sort(key=lambda d: d["primeiro_visto"] or "", reverse=True)
    OUT.write_text(json.dumps({
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "horas": horas,
        "itens": itens,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_obv = sum(1 for d in itens if d["obvio"])
    print(f"OK -> {OUT}  ({len(itens)} descartados em {horas} h; {n_obv} não-short/tamanho fora)")


if __name__ == "__main__":
    main()
