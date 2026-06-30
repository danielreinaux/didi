"""Gera a base de GABARITO da IA (Ville) — 50 itens diversos da última coleta.

O que faz:
  1. Lê data/coleta-ville-classificada.json.
  2. Faz uma amostra ESTRATIFICADA de 50 itens cobrindo motivos diversos
     (nao_ville, nao_short, sem_evidencia, padrao_outro, autenticidade_falsa,
     cor_liso_fora_whitelist, fecho_botao, fundo_gradiente, tamanho_invalido)
     e os tipos estruturais (tartaruga_grande/pequena/liso) — seed fixa, então
     a lista é REPRODUTÍVEL (rodar de novo dá os mesmos 50).
  3. Para cada item, extrai a resposta ATUAL da IA em cada um dos 10 critérios
     (pra mostrar ao lado do campo no front e alimentar o atalho "tudo = IA").
  4. Baixa as fotos pro repo (votacao/public/gabarito_fotos/<id>/) pra base não
     quebrar quando a URL do Vinted expirar.
  5. Emite votacao/public/gabarito_ville.json (lista congelada que o front lê).

Uso: python -m src.build.gabarito_ville [--n 50] [--seed 42]
"""
import json
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..classify.cor_ville import bucket_cor

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "votacao" / "public"
FOTOS_DIR = PUBLIC / "gabarito_fotos"
OUT = PUBLIC / "gabarito_ville.json"

N_ITENS = 50
SEED = 42
MAX_FOTOS = 6
# Garantias de diversidade estrutural (itens mais ricos pra testar a IA).
MIN_TARTARUGA = 4   # tartaruga_grande + tartaruga_pequena
MIN_LISO = 5
# Motivos raros mas valiosos pra testar — quase sempre vêm como motivo SECUNDÁRIO
# (ex.: "cor_liso_fora_whitelist, fecho_botao"), então o round-robin por rótulo
# nunca os pega. Garantimos até 2 de cada (enviesar pros casos difíceis).
MOTIVOS_RAROS = ("fecho_botao", "fecho_fivela", "fecho_velcro",
                 "fundo_gradiente", "tamanho_invalido", "desbotado")
MIN_POR_RARO = 2

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def _rotulo(item: dict) -> str:
    """Bucket de diversidade do item: o 'porquê' principal do descarte/estrutura.

    Usa o tipo nos casos de portão (nao_ville/nao_short/sem_evidencia/infantil) e,
    fora deles, o primeiro motivo_exclusao do score.
    """
    tipo = (item.get("classificacao") or {}).get("tipo")
    if tipo in ("nao_ville", "nao_short", "sem_evidencia", "infantil"):
        return tipo
    motivo = (item.get("score") or {}).get("motivo_exclusao") or ""
    primeiro = motivo.split(",")[0].strip()
    return primeiro or f"tipo_{tipo or 'desconhecido'}"


def _ia_etiqueta(item: dict) -> str | None:
    et = item.get("etiqueta") if isinstance(item.get("etiqueta"), dict) else {}
    val = et.get("tem_etiqueta")
    if val is True:
        return "sim"
    if val is False:
        return "nao"
    if "etiqueta" in et:  # rodou mas deu None/indefinido
        return "indefinido"
    return None  # nem rodou


def _ia_por_criterio(item: dict) -> dict:
    """Resposta ATUAL da IA em cada um dos 10 critérios (None = pipeline não avaliou)."""
    marca = item.get("marca_check") if isinstance(item.get("marca_check"), dict) else {}
    tart = item.get("tartaruga") if isinstance(item.get("tartaruga"), dict) else {}
    auth = item.get("autenticidade") if isinstance(item.get("autenticidade"), dict) else {}
    cor = item.get("cor") if isinstance(item.get("cor"), dict) else {}
    cordao = item.get("cordao") if isinstance(item.get("cordao"), dict) else {}
    fecho = item.get("fecho") if isinstance(item.get("fecho"), dict) else {}

    cor_nome = cor.get("cor_principal") or tart.get("cor_principal")
    # Bucket de cor é derivado por regex (cor_ville.bucket_cor) — é o que o cliente
    # gabarita. Só calcula quando a IA viu alguma cor.
    cor_bucket = bucket_cor(cor_nome) if cor_nome else None

    return {
        "e_vilebrequin": marca.get("e_vilebrequin"),
        "e_short": marca.get("e_short"),
        "tipo": tart.get("tipo"),
        "fundo_padrao": tart.get("fundo_padrao"),
        "aparencia": tart.get("aparencia"),
        "autenticidade": auth.get("autenticidade"),
        # guarda o nome cru da cor junto pra mostrar de contexto no front
        "cor_bucket": cor_bucket,
        "cor_nome": cor_nome,
        "cordao_cor": cordao.get("cordao_cor"),
        "fecho": fecho.get("tipo_fechamento"),
        "etiqueta": _ia_etiqueta(item),
    }


def _amostra(itens: list[dict], n: int, seed: int) -> list[dict]:
    """Amostra estratificada e reprodutível: garante itens estruturais (tartaruga,
    liso) e depois preenche em round-robin pelos buckets de motivo."""
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

    # 1) Garantia estrutural: tartarugas e lisos (casos mais ricos pra testar).
    tartas = [x for x in itens if (x.get("classificacao") or {}).get("tipo") in ("tartaruga_grande", "tartaruga_pequena")]
    lisos = [x for x in itens if (x.get("classificacao") or {}).get("tipo") == "liso"]
    rng.shuffle(tartas)
    rng.shuffle(lisos)
    pega(tartas, MIN_TARTARUGA)
    pega(lisos, MIN_LISO)

    # 2) Garantia dos motivos raros (aparecem como motivo secundário no score).
    for raro in MOTIVOS_RAROS:
        pool = [x for x in itens
                if raro in ((x.get("score") or {}).get("motivo_exclusao") or "")
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
                it = grupos[k].pop()
                usados.add(str(it.get("id")))
                escolhidos.append(it)

    return escolhidos[:n]


def _ext_por_magic(dados: bytes) -> str:
    if dados[:3] == b"\xff\xd8\xff":
        return "jpg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return "jpg"


def _baixar_fotos(iid: str, urls: list[str]) -> list[str]:
    """Baixa até MAX_FOTOS pro repo. Retorna lista de caminhos (local quando deu
    certo, URL remota como fallback quando falhou). Idempotente."""
    destino = FOTOS_DIR / iid
    destino.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for i, url in enumerate(urls[:MAX_FOTOS]):
        # Já existe? reaproveita (qualquer extensão).
        existente = next((p for p in destino.glob(f"{i}.*")), None)
        if existente:
            out.append(f"/gabarito_fotos/{iid}/{existente.name}")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                dados = resp.read()
            ext = _ext_por_magic(dados)
            arq = destino / f"{i}.{ext}"
            arq.write_bytes(dados)
            out.append(f"/gabarito_fotos/{iid}/{arq.name}")
        except Exception as e:
            print(f"      ! falha foto {i} do {iid}: {e}", flush=True)
            out.append(url)  # fallback: mantém a URL remota
    return out


def main() -> None:
    n, seed = N_ITENS, SEED
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--n" and i + 1 < len(args):
            n = int(args[i + 1])
        if a == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])

    inp = DATA / "coleta-ville-classificada.json"
    if not inp.exists():
        print("coleta-ville-classificada.json não encontrado.")
        sys.exit(1)

    itens = json.loads(inp.read_text(encoding="utf-8"))
    # só itens classificados de verdade (com fotos pra avaliar)
    itens = [x for x in itens if x.get("fotos") and (x.get("classificacao") or {}).get("tipo")]
    print(f"=== Gabarito Ville · {len(itens)} itens elegíveis · amostrando {n} (seed {seed}) ===\n")

    amostra = _amostra(itens, n, seed)

    # distribuição final pra conferência
    from collections import Counter
    dist = Counter(_rotulo(x) for x in amostra)
    print("Distribuição da amostra (por motivo/estrutura):")
    for k, v in dist.most_common():
        print(f"  {k}: {v}")
    print()

    print("Baixando fotos pro repo (pode demorar)…")
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
        "fonte": "coleta-ville-classificada.json",
        "total": len(saida),
        "itens": saida,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOK -> {OUT}  ({len(saida)} itens)")
    print(f"Fotos em -> {FOTOS_DIR}")


if __name__ == "__main__":
    main()
