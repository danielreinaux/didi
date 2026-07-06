"""Re-roda gpt-4o nos lisos estruturalmente ambíguos.

O modelo retorna confianca≈0.9 pra tudo — usamos critérios estruturais:
  - sem listra E sem bicolor (possível painel não detectado)
  - listra_na_frente = True (confirmar)
  - comprável sem brilhoso/bicolor detectado (double-check)

Uso: python -m src.reclassify_ambiguos [--workers N]
"""
import hashlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .tipo import _get_client
from ..config import IA
from ..prompts import liso_vs_estampado as prompt
from .elastico import verificar_elastico
from ..utils.listra_tier import avaliar_combo
from ..utils.ratelimit import pace_gpt4o
from ..utils.cost_tracker import track as _track, _dados as _ct_dados, PRECOS as _PRECOS
from .score import calcular_score

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-classificada.json"

_lock = threading.Lock()
MODEL_FORTE = "gpt-4o"


def _log(msg: str) -> None:
    with _lock:
        print(msg, flush=True)


def _fotos_fingerprint(item: dict) -> str:
    """Impressão digital das fotos do item. Muda quando o re-scrape traz imagens
    diferentes — é o que nos deixa saber se o item já foi conferido com ESTAS
    fotos (pula, economiza gpt-4o) ou se vale re-conferir (fotos novas)."""
    fotos = item.get("fotos") or []
    return hashlib.md5("|".join(fotos).encode("utf-8")).hexdigest()[:12]


def _is_ambiguo(item: dict) -> bool:
    cl = item.get("classificacao") or {}
    if cl.get("tipo") != "liso":
        return False

    # Já conferido com gpt-4o NAS MESMAS fotos → não reprocessa (economia).
    # Antes, reprocessava todos os ambíguos do acervo toda run, mesmo os já
    # conferidos (100% redundante). Só volta a ser ambíguo se as fotos mudarem.
    if cl.get("_model") == MODEL_FORTE and cl.get("_dc_fotos") == _fotos_fingerprint(item):
        return False

    bicolor = cl.get("bicolor", False)
    brilhoso = cl.get("tecido_brilhoso", False)
    listra = cl.get("tem_listra_lateral_sundek", False)
    listra_frente = cl.get("listra_na_frente", False)
    score_decisao = (item.get("score") or {}).get("decisao", "")

    # Sem listra E sem bicolor — pode ter painel bicolor não detectado
    if not listra and not bicolor:
        return True
    # Listra na frente detectada — confirmar com modelo mais forte
    if listra_frente:
        return True
    # Comprável mas sem brilhoso nem bicolor detectado — vale double-check
    if score_decisao == "compravel" and not brilhoso and not bicolor:
        return True

    return False


def _classificar_forte(item: dict) -> dict:
    """Chama gpt-4o para reclassificar liso/estampado."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {}

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_gpt4o()
    resp = _get_client().chat.completions.create(
        model=MODEL_FORTE,
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=200,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {}

    usage = resp.usage
    parsed["_usage"] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
    }
    return parsed


def _processar(item: dict, idx: int, total: int) -> dict:
    titulo = (item.get("titulo") or "")[:40]
    prefix = f"  [{idx}/{total}] {titulo}"

    try:
        c = _classificar_forte(item)
        usage = c.pop("_usage", {})

        # Contabiliza o custo do double-check no cost_tracker global — antes essa
        # etapa não passava pelo tracker e o gasto com gpt-4o ficava invisível.
        if usage:
            _track("reclassify_gpt4o", MODEL_FORTE,
                   usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

        if not c:
            _log(f"{prefix} → SKIP (sem resposta)")
            return item

        cl_atual = item.get("classificacao") or {}
        cl_anterior = {
            "bicolor": cl_atual.get("bicolor"),
            "brilhoso": cl_atual.get("tecido_brilhoso"),
            "listra_frente": cl_atual.get("listra_na_frente"),
        }

        cores_listras = c.get("cores_listras") or []
        cl_atual["cores_listras"] = cores_listras
        cl_atual["tem_listra_lateral_sundek"] = c.get("tem_listra_lateral_sundek", cl_atual.get("tem_listra_lateral_sundek"))
        cl_atual["tecido_brilhoso"] = c.get("tecido_brilhoso", False)
        cl_atual["tem_bolso_frontal"] = c.get("tem_bolso_frontal", False)
        cl_atual["listra_na_frente"] = c.get("listra_na_frente", False)
        cl_atual["bicolor"] = c.get("bicolor", False)
        cl_atual["confianca"] = c.get("confianca", cl_atual.get("confianca"))
        cl_atual["_model"] = MODEL_FORTE
        cl_atual["_dc_fotos"] = _fotos_fingerprint(item)  # marca as fotos conferidas

        # Recalcula combo tier
        cor_atual = item.get("cor") or {}
        if not isinstance(cor_atual, dict):
            cor_atual = {}
        tier_ia = cor_atual.get("tier", "ok")
        cor_nome = cor_atual.get("cor_principal", "")
        combo = avaliar_combo(cor_nome, cores_listras, tier_ia)
        cor_atual["cores_listras"] = cores_listras
        cor_atual["listra_tier"] = combo["listra_tier"]
        cor_atual["tier_final"] = combo["tier_final"]
        cor_atual["combo_motivo"] = combo["motivo"]

        # Detecta mudanças
        mudancas = []
        if cl_atual.get("bicolor") != cl_anterior["bicolor"]:
            mudancas.append(f"bicolor {cl_anterior['bicolor']}→{cl_atual.get('bicolor')}")
        if cl_atual.get("tecido_brilhoso") != cl_anterior["brilhoso"]:
            mudancas.append(f"brilhoso {cl_anterior['brilhoso']}→{cl_atual.get('tecido_brilhoso')}")
        if cl_atual.get("listra_na_frente") != cl_anterior["listra_frente"]:
            mudancas.append(f"listra_frente {cl_anterior['listra_frente']}→{cl_atual.get('listra_na_frente')}")

        flags = " ⚡ " + ", ".join(mudancas) if mudancas else ""
        tok = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        _log(f"{prefix} → conf={c.get('confianca','?')} tokens={tok}{flags}")

        novo_item = {**item, "classificacao": cl_atual, "cor": cor_atual}
        novo_item["score"] = calcular_score(novo_item)
        return novo_item

    except Exception as e:
        _log(f"{prefix} → ERRO: {str(e)[:80]}")
        return item


def main() -> None:
    workers = 4  # gpt-4o tem rate limits menores
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--workers" and i + 1 < len(sys.argv[1:]):
            workers = int(sys.argv[i + 2])

    todos = json.loads(PATH.read_text())
    ambiguos = [(i, item) for i, item in enumerate(todos) if _is_ambiguo(item)]

    print(f"Itens ambíguos para re-classificar com {MODEL_FORTE}: {len(ambiguos)}")
    print(f"Workers: {workers}\n")

    resultados: dict[int, dict] = {}
    total_tokens = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_processar, item, n + 1, len(ambiguos)): i
                   for n, (i, item) in enumerate(ambiguos)}
        for fut in as_completed(futures):
            orig_i = futures[fut]
            try:
                r = fut.result()
                resultados[orig_i] = r
            except Exception as e:
                _log(f"  ERRO futuro: {e}")

            if len(resultados) % 20 == 0:
                out = list(todos)
                for idx, r in resultados.items():
                    out[idx] = r
                with _lock:
                    PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))
                _log(f"\n  💾 Checkpoint: {len(resultados)}/{len(ambiguos)}\n")

    # Salva final
    out = list(todos)
    for idx, r in resultados.items():
        out[idx] = r
    PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # Stats
    novos_bicolor = sum(1 for r in resultados.values()
                        if (r.get("classificacao") or {}).get("bicolor") and
                        not (todos[list(resultados.keys())[list(resultados.values()).index(r)]].get("classificacao") or {}).get("bicolor"))
    novos_brilhosos = sum(1 for r in resultados.values()
                          if (r.get("classificacao") or {}).get("tecido_brilhoso"))
    novos_listra_frente = sum(1 for r in resultados.values()
                               if (r.get("classificacao") or {}).get("listra_na_frente"))

    from collections import Counter
    decisoes = Counter((it.get("score") or {}).get("decisao", "") for it in out)

    # Custo desta etapa (agora rastreado no cost_tracker) — deixa de ser invisível.
    d = _ct_dados.get("reclassify_gpt4o", {}).get(MODEL_FORTE, {"in": 0, "out": 0, "calls": 0})
    p = _PRECOS.get(MODEL_FORTE, {"in": 0, "out": 0})
    usd = (d["in"] / 1_000_000) * p["in"] + (d["out"] / 1_000_000) * p["out"]

    print(f"\n✅ Concluído: {len(ambiguos)} ambíguos reprocessados com {MODEL_FORTE}")
    print(f"   Custo double-check: ${usd:.4f} (~R${usd * 5:.2f}) · "
          f"{d['calls']} chamadas · {d['in']:,} tok in / {d['out']:,} tok out")
    print(f"   Bicolor detectados: {novos_brilhosos}")
    print(f"   Brilhosos detectados: {novos_brilhosos}")
    print(f"   Listra na frente detectados: {novos_listra_frente}")
    print(f"\n   Comprável: {decisoes['compravel']} | Médio: {decisoes['medio']} | Descartado: {decisoes['descartado']}")
    print(f"   Salvo em {PATH}")


if __name__ == "__main__":
    main()
