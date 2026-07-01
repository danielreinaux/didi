"""Gera a base de GABARITO da IA (Sundek) — 50 shorts diversos da última coleta.

Espelha o gabarito_ville.py, mas com os 14 critérios da Sundek (marca, tipo,
aparência, tecido brilhoso, listra, bicolor, tier de cor, elástico, fechamento,
bolso traseiro, patch com nome, bolso frontal, etiqueta).

Amostra ESTRATIFICADA por causa de descarte (estampado, nao_short, cor_ruim,
sem_elastico, bolso_so_logo, sem_listra, tecido_brilhoso, bicolor, desbotado,
fechamento_botao, ...) + garante alguns COMPRÁVEIS (casos bons de referência) e
os motivos RAROS. Seed fixa → reprodutível.

Uso: python -m src.build.gabarito_sundek [--n 50] [--seed 42]
"""
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .gabarito_ville import _baixar_fotos, FOTOS_DIR  # reusa download de fotos

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "votacao" / "public"
OUT = PUBLIC / "gabarito_sundek.json"

N_ITENS = 50
SEED = 42
# Casos "bons" de referência (a IA acertou em manter) — enriquecem a base.
MIN_COMPRAVEL = 4
MIN_MEDIO = 2
# Motivos raros mas valiosos pra testar (enviesar pros casos difíceis).
MOTIVOS_RAROS = ("fechamento_botao", "fechamento_velcro", "bicolor", "tecido_brilhoso",
                 "sem_bolso_traseiro", "bolso_frontal", "listra_na_frente", "desbotado",
                 "infantil", "tamanho_XS", "tamanho_XXL", "nao_sundek")
MIN_POR_RARO = 2


def _rotulo(item: dict) -> str:
    """Bucket de diversidade: motivo primário do descarte (ou decisão boa)."""
    s = item.get("score") or {}
    dec = s.get("decisao")
    if dec in ("compravel", "medio"):
        return f"OK_{dec}"
    motivo = s.get("motivo_exclusao") or s.get("motivo") or ""
    primeiro = motivo.split(",")[0].strip()
    if primeiro.startswith("preço") or primeiro.startswith("pre�") or "acima do teto" in primeiro:
        return "preco_acima_teto"
    return primeiro or (item.get("classificacao") or {}).get("tipo") or "desconhecido"


def _b(val):
    """bool → sim/nao; None explícito → indefinido; ausente tratado fora."""
    if val is True:
        return "sim"
    if val is False:
        return "nao"
    return "indefinido"


def _ia_por_criterio(item: dict) -> dict:
    """Resposta ATUAL da IA nos 14 critérios (None = pipeline não avaliou)."""
    marca = item.get("marca_check") if isinstance(item.get("marca_check"), dict) else {}
    cl = item.get("classificacao") if isinstance(item.get("classificacao"), dict) else {}
    cor = item.get("cor") if isinstance(item.get("cor"), dict) else {}
    elas = item.get("elastico") if isinstance(item.get("elastico"), dict) else {}
    etiq = item.get("etiqueta") if isinstance(item.get("etiqueta"), dict) else {}

    # Listra: listra_real / piping / sem_listra (None se a etapa não rodou).
    if "tem_listra_lateral_sundek" in cl:
        if cl.get("tem_listra_lateral_sundek"):
            listra = "listra_real"
        elif cl.get("e_piping"):
            listra = "piping"
        else:
            listra = "sem_listra"
    else:
        listra = None

    tier = cor.get("tier")
    if tier in ("erro", None):
        tier = None

    def campo(bloco, chave):
        """sim/nao/indefinido se presente; None se a etapa nem rodou."""
        return _b(bloco.get(chave)) if chave in bloco else None

    return {
        "e_sundek": marca.get("e_sundek"),
        "e_short": marca.get("e_short"),
        "tipo": cl.get("tipo"),
        "aparencia": cl.get("aparencia"),
        "tecido_brilhoso": campo(cl, "tecido_brilhoso"),
        "listra": listra,
        "bicolor": campo(cl, "bicolor"),
        "cor_tier": tier,
        "cor_nome": cor.get("cor_principal"),  # contexto no front
        "tem_elastico": campo(elas, "tem_elastico"),
        "fechamento": elas.get("tipo_fechamento"),
        "bolso_traseiro": campo(cl, "tem_bolso_traseiro"),
        "bolso_nome": campo(cl, "bolso_traseiro_tem_nome"),
        "bolso_frontal": campo(cl, "tem_bolso_frontal"),
        "etiqueta": campo(etiq, "tem_etiqueta"),
    }


def _amostra(itens: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    escolhidos: list[dict] = []
    usados: set[str] = set()

    def pega(pool: list[dict], limite: int) -> None:
        tomados = 0
        for it in pool:
            if len(escolhidos) >= n or tomados >= limite:
                break
            iid = str(it.get("id"))
            if iid not in usados:
                usados.add(iid)
                escolhidos.append(it)
                tomados += 1

    def por_decisao(dec):
        return [x for x in itens if (x.get("score") or {}).get("decisao") == dec]

    # 1) Casos bons de referência.
    comp = por_decisao("compravel"); rng.shuffle(comp); pega(comp, MIN_COMPRAVEL)
    med = por_decisao("medio"); rng.shuffle(med); pega(med, MIN_MEDIO)

    # 2) Motivos raros (biased pros casos difíceis).
    for raro in MOTIVOS_RAROS:
        pool = [x for x in itens
                if raro in ((x.get("score") or {}).get("motivo_exclusao")
                            or (x.get("score") or {}).get("motivo") or "")
                and str(x.get("id")) not in usados]
        rng.shuffle(pool)
        pega(pool, MIN_POR_RARO)

    # 3) Round-robin pelos buckets de motivo até fechar n.
    grupos: dict[str, list[dict]] = {}
    for it in itens:
        if str(it.get("id")) in usados:
            continue
        grupos.setdefault(_rotulo(it), []).append(it)
    for pool in grupos.values():
        rng.shuffle(pool)
    ordem = sorted(grupos.keys())
    rng.shuffle(ordem)
    while len(escolhidos) < n and any(grupos[k] for k in ordem):
        for k in ordem:
            if len(escolhidos) >= n:
                break
            if grupos[k]:
                escolhidos.append(grupos[k].pop())

    return escolhidos[:n]


def main() -> None:
    n, seed = N_ITENS, SEED
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--n" and i + 1 < len(args):
            n = int(args[i + 1])
        if a == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])

    inp = DATA / "coleta-classificada.json"
    if not inp.exists():
        print("coleta-classificada.json não encontrado.")
        sys.exit(1)

    itens = json.loads(inp.read_text(encoding="utf-8"))
    # elegíveis: classificados de verdade (fora erro/nao_classificado) e com fotos
    itens = [x for x in itens
             if x.get("fotos")
             and (x.get("classificacao") or {}).get("tipo") not in (None, "erro")
             and (x.get("score") or {}).get("decisao") != "nao_classificado"]
    print(f"=== Gabarito Sundek · {len(itens)} itens elegíveis · amostrando {n} (seed {seed}) ===\n")

    amostra = _amostra(itens, n, seed)
    dist = Counter(_rotulo(x) for x in amostra)
    print("Distribuição da amostra (por causa/decisão):")
    for k, v in dist.most_common():
        print(f"  {k}: {v}")
    print()

    print("Baixando fotos pro repo…")
    saida = []
    for idx, it in enumerate(amostra, 1):
        iid = str(it.get("id"))
        fotos = _baixar_fotos(iid, it.get("fotos") or [])
        saida.append({
            "id": iid,
            "url": it.get("url"),
            "titulo": it.get("titulo"),
            "tamanho": it.get("tamanho"),
            "estado": it.get("estado"),
            "preco": it.get("preco_total") or it.get("preco"),
            "bucket": _rotulo(it),
            "fotos": fotos,
            "ia": _ia_por_criterio(it),
        })
        print(f"  [{idx:02d}/{len(amostra)}] {iid} · {len(fotos)} fotos · {_rotulo(it)}", flush=True)

    doc = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "fonte": "coleta-classificada.json",
        "total": len(saida),
        "itens": saida,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOK -> {OUT}  ({len(saida)} itens)")
    print(f"Fotos em -> {FOTOS_DIR}")


if __name__ == "__main__":
    main()
