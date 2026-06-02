"""Pipeline de classificação para Vilebrequin.

Lê data/coleta-ville.json, classifica cada item via OpenAI Vision,
salva em data/coleta-ville-classificada.json.

Pipeline por item:
  1. Prefilter de título (regex, sem IA)
  2. Verifica marca Vilebrequin + autenticidade (vision, gpt-4o)
  3. Classifica tartaruga: grande / pequena / liso / outro (vision, gpt-4o-mini)
  4. Cor tier (vision — reutiliza classify_color)
  5. Etiqueta (vision — reutiliza classify_etiqueta)

Uso: python -m src.classify_ville_run [--workers N]   (padrão: 4)
"""
import json
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Console do Windows é cp1252 e quebra em ✓/✗/🐢 — força UTF-8 na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .ville_brand import verificar_ville
from .tartaruga import classificar_tartaruga
from .autenticidade_ville import verificar_autenticidade
from .cor import classificar_cor
from .etiqueta import verificar_etiqueta
from .score_ville import calcular_score

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

_print_lock = threading.Lock()
_counters_lock = threading.Lock()

# Palavras-chave que indicam que o título é provavelmente Vilebrequin
_VILLE_RE = re.compile(
    r"vilebrequin|vile[- ]?brequin|villebrequin|vilebreq|vbrequin|v\.?b\.",
    re.IGNORECASE,
)


def _parece_ville(item: dict) -> tuple[bool, str]:
    titulo = (item.get("titulo") or "").lower()
    if _VILLE_RE.search(titulo):
        return True, ""
    return False, "titulo sem Vilebrequin"


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def _salvar(resultados: list, itens_orig: list, ja_processados: dict, path: Path) -> None:
    por_idx = {i: r for i, r in resultados}
    out = []
    for i, item in enumerate(itens_orig):
        if i in por_idx:
            out.append(por_idx[i])
        elif item.get("id") in ja_processados:
            out.append(ja_processados[item["id"]])
        else:
            out.append(item)
    with _print_lock:
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def _processar(item: dict, idx: str, total: int) -> tuple[dict, int, int]:
    titulo = (item.get("titulo") or "")[:50]
    prefix = f"  [{idx}/{total}] {titulo}"
    in_tok = out_tok = 0

    if item.get("erro"):
        _log(f"{prefix} → SKIP (item com erro)")
        return item, 0, 0

    # 1. Prefilter
    ok, motivo = _parece_ville(item)
    if not ok:
        _log(f"{prefix} → × NAO-VILLE [{motivo}]")
        return {**item, "classificacao": {"tipo": "nao_ville", "motivo": motivo, "confianca": 1}}, 0, 0

    # 2. Marca + autenticidade
    try:
        marca = verificar_ville(item)
        u = marca.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
    except Exception as e:
        marca = {"e_vilebrequin": "indefinido", "autenticidade": "indefinido", "evidencia": f"erro: {e}", "confianca": 0}

    if marca.get("e_vilebrequin") == "nao":
        _log(f"{prefix} → × NAO-VILEBREQUIN")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_vilebrequin", "confianca": marca.get("confianca", 1)}}, in_tok, out_tok

    if marca.get("e_short") == "nao":
        _log(f"{prefix} → × NAO-SHORT")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_short", "confianca": marca.get("confianca", 1)}}, in_tok, out_tok

    # 3. Tartaruga (padrão de estampa)
    try:
        tartaruga = classificar_tartaruga(item)
        u = tartaruga.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
    except Exception as e:
        tartaruga = {"tipo": "indefinido", "justificativa": f"erro: {e}", "confianca": 0}

    tipo_tart = tartaruga.get("tipo", "indefinido")
    tag_tart = {
        "tartaruga_grande": "🐢 GRANDE",
        "tartaruga_pequena": "~ peq",
        "liso": "LISO",
        "outro": "OUTRO",
        "indefinido": "? indef",
    }.get(tipo_tart, "?")

    # 4. Autenticidade dedicada (zoom no bolso traseiro — critério central da marca).
    # Pula a chamada de IA quando o short é liso (sem padrão pra continuar no bolso)
    # ou quando o padrão é indefinido — economiza ~$0.03/item.
    if tipo_tart == "liso":
        autenticidade = {"autenticidade": "indefinido",
                         "evidencia": "short liso — sem padrão de referência no bolso"}
    elif tipo_tart == "indefinido":
        autenticidade = {"autenticidade": "indefinido",
                         "evidencia": "padrão indefinido — não dá pra avaliar o bolso"}
    else:
        try:
            autenticidade = verificar_autenticidade(item)
            u = autenticidade.pop("_usage", {})
            in_tok += u.get("prompt_tokens", 0)
            out_tok += u.get("completion_tokens", 0)
        except Exception as e:
            autenticidade = {"autenticidade": "indefinido", "evidencia": f"erro: {e}"}

    auth_val = autenticidade.get("autenticidade", "indefinido")
    auth_tag = {
        "original": "✓ orig",
        "falso": "✗ FALSO",
        "suspeito": "~ sus",
        "sem_foto_bolso": "? s/bolso",
        "indefinido": "? indef",
    }.get(auth_val, "?")

    linha = f"{prefix} → {auth_tag} | {tag_tart} conf={tartaruga.get('confianca')}"

    cor = etiqueta = None

    # 4. Cor (sempre — Ville não tem critério de listras)
    try:
        cor = classificar_cor(item)
        u = cor.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        linha += f" | cor={cor.get('cor_principal')} [{cor.get('tier')}]"
    except Exception as e:
        cor = {"tier": "erro", "erro": str(e)}

    # 5. Etiqueta
    try:
        etiqueta = verificar_etiqueta(item)
        u = etiqueta.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        if etiqueta.get("tem_etiqueta") is True:
            linha += " | etiq✓"
        elif etiqueta.get("tem_etiqueta") is False:
            linha += " | sem-etiq"
    except Exception as e:
        etiqueta = {"tem_etiqueta": None, "erro": str(e)}

    resultado = {
        **item,
        "marca_check": marca,
        "tartaruga": tartaruga,
        "autenticidade": autenticidade,
        "cor": cor,
        "etiqueta": etiqueta,
        "classificacao": {"tipo": tipo_tart, "autenticidade": auth_val},
    }
    resultado["score"] = calcular_score(resultado)
    s = resultado["score"]
    linha += f" | {s.get('decisao')} ({s.get('score')})"
    _log(linha)
    return resultado, in_tok, out_tok


def main() -> None:
    inp = DATA / "coleta-ville.json"
    if not inp.exists():
        print("coleta-ville.json não encontrado. Rode `python -m src.scrape_ville` primeiro.")
        sys.exit(1)

    workers = 4
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--workers" and i + 1 < len(sys.argv[1:]):
            workers = int(sys.argv[i + 2])

    itens = json.loads(inp.read_text(encoding="utf-8"))
    total = len(itens)
    print(f"=== Classificação Vilebrequin · {total} itens · {workers} workers ===\n")

    t0 = time.time()
    resultados: list[tuple[int, dict]] = []
    input_tokens = output_tokens = 0

    checkpoint_path = DATA / "coleta-ville-classificada.json"
    ja_processados: dict[str, dict] = {}
    if checkpoint_path.exists():
        try:
            for x in json.loads(checkpoint_path.read_text(encoding="utf-8")):
                if x.get("id") and (x.get("classificacao") or {}).get("tipo") not in (None, "erro"):
                    ja_processados[x["id"]] = x
        except Exception:
            pass

    pendentes = [(i, item) for i, item in enumerate(itens) if item.get("id") not in ja_processados]
    pulados = total - len(pendentes)
    if pulados:
        print(f"  {pulados} itens já classificados — pulando. {len(pendentes)} pendentes.\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_processar, item, f"{orig_i+1:03d}", total): (orig_i, item)
            for orig_i, item in pendentes
        }
        concluidos = 0
        for fut in as_completed(futures):
            orig_i, item_orig = futures[fut]
            try:
                resultado, in_t, out_t = fut.result()
            except Exception as e:
                resultado = {**item_orig, "classificacao": {"tipo": "erro", "erro": str(e)}}
                in_t = out_t = 0
            resultados.append((orig_i, resultado))
            with _counters_lock:
                input_tokens += in_t
                output_tokens += out_t
                concluidos += 1
                if concluidos % 10 == 0:
                    _salvar(resultados, itens, ja_processados, checkpoint_path)

    _salvar(resultados, itens, ja_processados, checkpoint_path)

    # Pass final: garante que TODO item tenha score (inclusive os cacheados de
    # rodadas antigas, que foram pulados e podem não ter passado pelo score_ville).
    out = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    mudou = False
    for x in out:
        if "score" not in x and (x.get("classificacao") or {}).get("tipo"):
            x["score"] = calcular_score(x)
            mudou = True
    if mudou:
        checkpoint_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    cnt = lambda t: sum(1 for x in out if (x.get("classificacao") or {}).get("tipo") == t)
    dec = lambda d: sum(1 for x in out if (x.get("score") or {}).get("decisao") == d)

    in_usd = (input_tokens / 1_000_000) * 0.15
    out_usd = (output_tokens / 1_000_000) * 0.60
    total_usd = in_usd + out_usd

    print("\n=== Resumo ===")
    print(f"  ✓ Compráveis:      {dec('compravel')}")
    print(f"  ~ Médios:          {dec('medio')}")
    print(f"  ✗ Descartados:     {dec('descartado')}")
    print(f"  ⟳ Não classific.:  {dec('nao_classificado')}")
    print(f"  ---")
    print(f"  Tartaruga grande:  {cnt('tartaruga_grande')}")
    print(f"  Tartaruga pequena: {cnt('tartaruga_pequena')}")
    print(f"  Lisos:             {cnt('liso')}")
    print(f"  Outros padrões:    {cnt('outro')}")
    print(f"  Falsos:            {cnt('falso')}")
    print(f"  Não-Vilebrequin:   {cnt('nao_vilebrequin')}")
    print(f"  Não-shorts:        {cnt('nao_short')}")
    print(f"  Indefinidos:       {cnt('indefinido')}")
    print(f"  Erros:             {cnt('erro')}")
    print(f"  Tokens IN:         {input_tokens:,}")
    print(f"  Tokens OUT:        {output_tokens:,}")
    print(f"  Custo:             ${total_usd:.5f} (~R$ {total_usd * 5:.3f})")
    print(f"  Duração:           {time.time() - t0:.1f}s")
    print(f"\n  Salvo em data/coleta-ville-classificada.json")


if __name__ == "__main__":
    main()
