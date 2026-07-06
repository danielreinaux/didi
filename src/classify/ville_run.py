"""Pipeline de classificação para Vilebrequin.

Lê data/coleta-ville.json, classifica cada item via OpenAI Vision,
salva em data/coleta-ville-classificada.json.

Pipeline por item:
  1. Prefilter de título (regex, sem IA)
  2. Verifica marca Vilebrequin + autenticidade (vision, gpt-4o)
  3. Classifica tartaruga: grande / pequena / liso / outro (vision, gpt-4o-mini)
  4. Cor tier (vision — reutiliza classify_color)
  5. Etiqueta (vision — reutiliza classify_etiqueta)
  6. Cordão: cor do drawstring → coleção antiga (cinza) no score (gpt-4o-mini)
  7. Fecho: cordão/elástico OK; botão/fivela/velcro → descarte (vision, gpt-4o)

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
from .cordao_ville import verificar_cordao
from .fecho_ville import verificar_fecho
from .etiqueta import verificar_etiqueta
from .score_ville import calcular_score, _tamanho_key
# Reusa as exclusões de título do Sundek (infantil, não-short) — P2.
from .prefilter import EXCLUSAO, EXCLUSAO_INFANTIL

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

_print_lock = threading.Lock()
_counters_lock = threading.Lock()

# Palavras-chave que indicam que o título é provavelmente Vilebrequin
_VILLE_RE = re.compile(
    r"vilebrequin|vile[- ]?brequin|villebrequin|vilebreq|vbrequin|v\.?b\.",
    re.IGNORECASE,
)

# Indício de que há um SHORT no anúncio (mesmo que o título cite t-shirt/polo).
# Salva os "Ensemble Homme T-shirt + Short de bain Tortues" — conjuntos que
# incluem o short comprável (o doc cita 'Ensemble...' como comprável clássico).
_SHORT_HINT = re.compile(
    r"\bshorts?\b|maillot|\bbain\b|bermuda|\bswim\b|costume\s+da\s+bagno|"
    r"zwembroek|badebroek|ba[ñn]ador|\bmare\b",
    re.IGNORECASE,
)


def marca_sem_evidencia(marca: dict) -> bool:
    """True quando a IA não viu nem marca nem formato nas fotos (ex.: paisagem/palmeira).

    Duas regras cobrem o caso:
      (1) marca indefinida com confianca ZERO (IA sinalizou "não vi nada");
      (2) AMBOS marca e formato indefinidos com confianca baixa (<0.4).
    """
    e_vb = marca.get("e_vilebrequin")
    e_sh = marca.get("e_short")
    conf = marca.get("confianca") or 0
    return (e_vb == "indefinido" and conf == 0) or (
        e_vb == "indefinido" and e_sh == "indefinido" and conf < 0.4
    )


def _parece_ville(item: dict) -> tuple[bool, str, str]:
    """Prefilter de título (regex, sem IA). Retorna (ok, tipo, motivo).

    Corta de graça, antes de gastar visão:
      - título sem "vilebrequin"        → nao_ville
      - infantil (X ans, kids, etc.)     → infantil
      - não-short (polo, camiseta, sunga…) → nao_short
    tipo é "" quando ok=True.
    """
    titulo = (item.get("titulo") or "").strip()
    if not titulo:
        return False, "nao_ville", "sem título"
    if not _VILLE_RE.search(titulo.lower()):
        return False, "nao_ville", "titulo sem Vilebrequin"
    for regex, motivo in EXCLUSAO_INFANTIL:
        if regex.search(titulo):
            return False, "infantil", motivo
    # Se o título também menciona short/maillot/bain, é provável conjunto
    # (ex: "Ensemble T-shirt + Short de bain") → não exclui, deixa a IA decidir.
    tem_short = bool(_SHORT_HINT.search(titulo))
    for regex, motivo in EXCLUSAO:
        if regex.search(titulo):
            if tem_short:
                continue
            return False, "nao_short", motivo
    return True, "", ""


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
    ok, tipo_pf, motivo = _parece_ville(item)
    if not ok:
        _log(f"{prefix} → × {tipo_pf.upper()} [{motivo}]")
        return {**item, "classificacao": {"tipo": tipo_pf, "motivo": motivo, "confianca": 1}}, 0, 0

    # 1b. Pré-check de tamanho (sem IA). O tamanho já vem do scrape (coleta-ville.json).
    # Se for inválido (XS / XXL+ / numérico / "talla única"), o item é descarte
    # garantido no score — mesma função _tamanho_key que o calcular_score usa, então a
    # decisão é idêntica, só antecipada. Corta AQUI, antes de qualquer visão, e economiza
    # marca+tartaruga+autenticidade+fecho (gpt-4o) num item que ia ser descartado igual.
    if _tamanho_key(item.get("tamanho"), item.get("titulo")) is None:
        _log(f"{prefix} → × TAMANHO [{item.get('tamanho')}]")
        return {**item, "classificacao": {"tipo": "tamanho_invalido",
                "motivo": f"tamanho {item.get('tamanho')!r} fora de S-XL", "confianca": 1}}, 0, 0

    # 2. Marca + autenticidade
    try:
        marca = verificar_ville(item)
        u = marca.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
    except Exception as e:
        marca = {"e_vilebrequin": "indefinido", "autenticidade": "indefinido", "evidencia": f"erro: {e}", "confianca": 0}

    if marca.get("e_vilebrequin") == "nao":
        _log(f"{prefix} → × NAO-VILLE (marca)")
        # P3: unifica com o prefilter — tudo que não é Vilebrequin vira nao_ville.
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_ville", "motivo": "marca diferente (visão)", "confianca": marca.get("confianca", 1)}}, in_tok, out_tok

    if marca.get("e_short") == "nao":
        _log(f"{prefix} → × NAO-SHORT")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_short", "confianca": marca.get("confianca", 1)}}, in_tok, out_tok

    # Sem evidência do produto: a IA não conseguiu ver nem marca nem formato
    # (ex.: única foto é de paisagem/palmeira). Descarta antes de gastar tartaruga/
    # autenticidade/cor/etiqueta — economiza ~4 chamadas de visão por item lixo.
    if marca_sem_evidencia(marca):
        _log(f"{prefix} → × SEM-EVIDENCIA [{marca.get('evidencia','')[:60]}]")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "sem_evidencia", "motivo": marca.get("evidencia") or "sem evidência visual do produto", "confianca": marca.get("confianca") or 0}}, in_tok, out_tok

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

    # Early-exit: padrão "outro" (peixe/coral/âncora/etc.) é descarte garantido no score
    # (EXCLUI_UPSTREAM → "padrao_outro_nao_compra"). Não vale gastar autenticidade (gpt-4o,
    # a etapa mais cara), cor, etiqueta, cordão e fecho (gpt-4o) — ~metade dos itens Ville
    # caem em "outro". Mesma ideia dos short-circuits de liso/indefinido logo abaixo, só que
    # mais cedo e completo. O score é calculado no passe final do main() (item sem "score").
    if tipo_tart == "outro":
        _log(f"{prefix} → {tag_tart} — descarte garantido, pula atributos")
        return {**item, "marca_check": marca, "tartaruga": tartaruga,
                "classificacao": {"tipo": "outro", "autenticidade": "indefinido"}}, in_tok, out_tok

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

    cor = etiqueta = cordao = None

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

    # 6. Cordão (cor do drawstring) — define coleção antiga (cinza) no score.
    try:
        cordao = verificar_cordao(item)
        u = cordao.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        cc = cordao.get("cordao_cor")
        if cc == "cinza":
            linha += " | cordão=cinza (antiga)"
        elif cc and cc != "indefinido":
            linha += f" | cordão={cc}"
    except Exception as e:
        cordao = {"cordao_cor": "indefinido", "erro": str(e)}

    # 7. Fecho (cordão/elástico = OK; botão/fivela/velcro → descarte no score).
    fecho = None
    try:
        fecho = verificar_fecho(item)
        u = fecho.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        tf = fecho.get("tipo_fechamento")
        if tf in ("botao", "fivela", "velcro"):
            linha += f" | fecho={tf}✗"
        elif tf and tf != "indefinido":
            linha += f" | fecho={tf}"
    except Exception as e:
        fecho = {"tipo_fechamento": "indefinido", "erro": str(e)}

    resultado = {
        **item,
        "marca_check": marca,
        "tartaruga": tartaruga,
        "autenticidade": autenticidade,
        "cor": cor,
        "etiqueta": etiqueta,
        "cordao": cordao,
        "fecho": fecho,
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

    # Persiste o custo deste run pra o relatório consolidado (src.build.relatorio_custo).
    # Sem isso o custo do Ville só vive no log do Actions e some. ⚠️ custo_usd é PISO:
    # preçamos tudo como mini, mas o Ville usa gpt-4o (17x mais caro) em vários passos.
    try:
        (DATA / "custo_ville.json").write_text(json.dumps({
            "tok_in": input_tokens,
            "tok_out": output_tokens,
            "calls": 0,  # ville_run não conta chamadas isoladas (vários calls por item)
            "custo_usd": round(total_usd, 6),
            "itens_processados": len(pendentes),
            "duracao_s": round(time.time() - t0, 1),
        }, indent=2), encoding="utf-8")
    except Exception:
        pass

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
    print(f"  Não-Ville:         {cnt('nao_ville')}")
    print(f"  Não-shorts:        {cnt('nao_short')}")
    print(f"  Infantis:          {cnt('infantil')}")
    print(f"  Indefinidos:       {cnt('indefinido')}")
    print(f"  Erros:             {cnt('erro')}")
    print(f"  Tokens IN:         {input_tokens:,}")
    print(f"  Tokens OUT:        {output_tokens:,}")
    print(f"  Custo:             ${total_usd:.5f} (~R$ {total_usd * 5:.3f})")
    print(f"  Duração:           {time.time() - t0:.1f}s")
    print(f"\n  Salvo em data/coleta-ville-classificada.json")


if __name__ == "__main__":
    main()
