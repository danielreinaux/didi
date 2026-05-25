"""Tracker de custo por etapa do pipeline. Thread-safe.

Cada chamada à OpenAI é registrada com (etapa, modelo, tokens_in, tokens_out).
No final, gera relatório mostrando onde foi cada dólar.
"""
import threading
from collections import defaultdict

# Preços OpenAI (USD por 1M tokens), Out/2025
PRECOS = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o":      {"in": 2.50, "out": 10.00},
}

_lock = threading.Lock()
# {etapa: {modelo: {"in": int, "out": int, "calls": int}}}
_dados: dict = defaultdict(lambda: defaultdict(lambda: {"in": 0, "out": 0, "calls": 0}))


def track(etapa: str, modelo: str, in_tok: int, out_tok: int) -> None:
    """Registra uma chamada. etapa = 'brand', 'classify', 'listra', 'color',
    'bolso', 'elastico', 'etiqueta', 'brand_4o_recheck', 'crop_localizar', etc."""
    with _lock:
        d = _dados[etapa][modelo]
        d["in"] += in_tok
        d["out"] += out_tok
        d["calls"] += 1


def reset() -> None:
    with _lock:
        _dados.clear()


def relatorio(total_itens: int = 0) -> str:
    """Gera string formatada com gastos por etapa."""
    with _lock:
        if not _dados:
            return "Nenhuma chamada registrada."

        # Ordena etapas pela ordem que aparecem no pipeline
        ordem = ["brand", "brand_4o_recheck", "classify", "color", "crop_localizar",
                 "listra", "elastico", "bolso", "etiqueta"]
        etapas_ord = [e for e in ordem if e in _dados] + [
            e for e in _dados if e not in ordem
        ]

        linhas = []
        linhas.append(f"\n{'═' * 78}")
        linhas.append(f"{'CUSTO POR ETAPA':^78}")
        linhas.append(f"{'═' * 78}")
        linhas.append(f"{'Etapa':<22} {'Modelo':<14} {'Chamadas':>10} {'Tok IN':>12} {'Tok OUT':>10} {'$':>8}")
        linhas.append(f"{'-' * 78}")

        total_usd = 0.0
        total_calls = 0
        total_in = 0
        total_out = 0

        for etapa in etapas_ord:
            for modelo, d in sorted(_dados[etapa].items()):
                p = PRECOS.get(modelo, {"in": 0, "out": 0})
                usd = (d["in"] / 1_000_000) * p["in"] + (d["out"] / 1_000_000) * p["out"]
                total_usd += usd
                total_calls += d["calls"]
                total_in += d["in"]
                total_out += d["out"]
                linhas.append(
                    f"{etapa:<22} {modelo:<14} {d['calls']:>10} "
                    f"{d['in']:>12,} {d['out']:>10,} ${usd:>7.4f}"
                )

        linhas.append(f"{'-' * 78}")
        linhas.append(
            f"{'TOTAL':<22} {'':<14} {total_calls:>10} {total_in:>12,} {total_out:>10,} ${total_usd:>7.4f}"
        )
        linhas.append(f"{'═' * 78}")
        if total_itens:
            por_item = total_usd / total_itens
            linhas.append(
                f"  {total_itens} itens processados → "
                f"${por_item:.4f}/item (~R${por_item * 5:.3f}/item)"
            )
            linhas.append(f"  Custo total: ${total_usd:.4f} (~R${total_usd * 5:.2f})")
        return "\n".join(linhas)


def dump_json() -> dict:
    """Retorna os dados crus pra salvar em arquivo."""
    with _lock:
        return {etapa: dict(d) for etapa, d in _dados.items()}
