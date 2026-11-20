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
from datetime import datetime, timedelta, timezone
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
from .autenticidade_ville import verificar_autenticidade, acertar_gravado
from .bolso_confere import conferir as conferir_bolso, precisa_conferir as precisa_conferir_bolso
from .cordao_ville import verificar_cordao
from .cor_fundo_ville import classificar_cor_fundo
from .fecho_ville import verificar_fecho
from .etiqueta import verificar_etiqueta
from .estado_ville import verificar_estado
from . import orientacao
from . import reanalise
from .score_ville import calcular_score, _tamanho_key
# Reusa as exclusões de título do Sundek (infantil, não-short) — P2.
from .prefilter import EXCLUSAO, EXCLUSAO_INFANTIL
from ..config import IA, VILLE_APP_DESDE, VILLE_LISO_OFERTA
# Custo REAL por etapa/modelo (o Ville usa gpt-4o em marca/tartaruga/autenticidade/
# fecho e mini no resto). Antes o custo era PISO — precificado como se fosse tudo mini.
from ..utils.cost_tracker import track as _track, dump_json as _dump_cost, reset as _reset_cost, relatorio as _relatorio_cost, PRECOS as _PRECOS

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

_print_lock = threading.Lock()
_counters_lock = threading.Lock()

# Palavras-chave que indicam que o título é provavelmente Vilebrequin. A 2ª alternativa pega
# os erros de grafia vistos no Vinted: vibrequin, vilbrequin, villebrekin, vilebreuin.
_VILLE_RE = re.compile(
    r"vilebrequin|vile[- ]?brequin|villebrequin|vilebreq|vbrequin|v\.?b\.|"
    r"vi(?:ll?)?e?[- ]?bre[qkc]?u?i?n",
    re.IGNORECASE,
)


def _marca_vinted(item: dict) -> str:
    """Marca cadastrada no Vinted, lida do resumo do card ("título+tamanho·estado·marca·
    Subido…"). O campo `marca` do scrape vem vazio. "" se não der para ler."""
    partes = [p.strip() for p in (item.get("resumo") or "").split("·")]
    estado = (item.get("estado") or "").strip()
    if estado and estado in partes:
        i = partes.index(estado)
        return partes[i + 1] if i + 1 < len(partes) else ""
    return partes[2] if len(partes) >= 3 else ""


def _marca_vinted_e_ville(item: dict) -> bool:
    return bool(_VILLE_RE.search(_marca_vinted(item)))

# Indício de que há um SHORT no anúncio (mesmo que o título cite t-shirt/polo).
# Salva os "Ensemble Homme T-shirt + Short de bain Tortues" — conjuntos que
# incluem o short comprável (o doc cita 'Ensemble...' como comprável clássico).
_SHORT_HINT = re.compile(
    r"\bshorts?\b|maillot|\bbain\b|bermuda|\bswim\b|costume\s+da\s+bagno|"
    r"zwembroek|badebroek|ba[ñn]ador|\bmare\b|\btrunks\b|\bswimming\b|\bswimwear\b",
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


def _falha_ia(x: dict) -> bool:
    """True se o anúncio ficou sem análise por FALHA de chamada (sem crédito, 429, timeout),
    não por decisão da IA: está marcado "erro", ou foi gravado "sem_evidencia" pelo código
    antigo, que tratava a exceção da marca como "a IA não viu nada" (na falta de saldo de
    15–16/11/2026, 27 anúncios foram descartados assim e nunca voltariam para a análise)."""
    cl = x.get("classificacao") or {}
    if cl.get("tipo") == "erro":
        return True
    evidencia = str((x.get("marca_check") or {}).get("evidencia") or "")
    return cl.get("tipo") == "sem_evidencia" and evidencia.startswith("erro:")


def _parece_ville(item: dict) -> tuple[bool, str, str]:
    """Prefilter de título (regex, sem IA). Retorna (ok, tipo, motivo).

    Corta de graça, antes de gastar visão:
      - título sem "vilebrequin" E marca do Vinted ≠ Vilebrequin → nao_ville
      - infantil (X ans, kids, etc.)     → infantil
      - não-short (polo, camiseta, sunga…) → nao_short
    tipo é "" quando ok=True.
    """
    titulo = (item.get("titulo") or "").strip()
    if not titulo:
        return False, "nao_ville", "sem título"
    # Título sozinho não basta (07/11/2026): "Maillot de bain", "Bañador caballero" e
    # "Vibrequin banadores" com a marca Vilebrequin no Vinted eram cortados sem a IA olhar
    # (23 em 7 dias). Com a marca cadastrada, a IA de marca confere pelas fotos.
    if not _VILLE_RE.search(titulo.lower()) and not _marca_vinted_e_ville(item):
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


def _salvar(resultados: list, itens_orig: list, acervo_previo: dict, path: Path) -> None:
    """Acumula por id: acervo prévio + resultados desta rodada (que sobrescrevem).
    Itens já vistos e AUSENTES do scrape atual são PRESERVADOS — nada se perde
    (espelha o Sundek). Antes a Ville reescrevia só o scrape atual, então item que
    saía da janela de raspagem sumia do acervo mesmo ainda à venda, e o passo
    `verifica_vendidos --marca ville` ficava sem candidatos pra revisitar/marcar.
    Marca status/timestamps; reaparecer no scrape reativa (status='ativo')."""
    por_idx = {i: r for i, r in resultados}
    agora = datetime.now(timezone.utc).isoformat()
    acervo = dict(acervo_previo)  # id -> item (cópia)
    for i, item in enumerate(itens_orig):
        rid = item.get("id")
        if not rid:
            continue  # stub de scrape sem id — não acumula
        if i in por_idx:
            novo = por_idx[i]
        elif rid in acervo:
            novo = acervo[rid]  # cacheado (fotos iguais) — mantém classificação
        else:
            novo = item
        prev = acervo.get(rid, {})
        novo["primeiro_visto"] = prev.get("primeiro_visto") or prev.get("coletado_em") or agora
        novo["ultimo_visto"] = agora
        novo["status"] = "ativo"  # reapareceu no scrape → ativo
        acervo[rid] = novo
    with _print_lock:
        path.write_text(json.dumps(list(acervo.values()), indent=2, ensure_ascii=False), encoding="utf-8")


def _processar(item: dict, idx: str, total: int) -> tuple[dict, int, int]:
    """Processa um item. O resultado sai com as URLs ORIGINAIS das fotos: os agentes podem
    ter visto versões postas em pé (classify/orientacao.py), que não vão para o acervo."""
    resultado, in_tok, out_tok = _processar_etapas(item, idx, total)
    return orientacao.restaurar(resultado), in_tok, out_tok


def _processar_etapas(item: dict, idx: str, total: int) -> tuple[dict, int, int]:
    """As etapas do pipeline. A partir da 2b, `item` pode ser a cópia com fotos giradas."""
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
        _track("marca", u.get("model") or IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    except Exception as e:
        # Falha de chamada não é "a IA não viu nada": marca erro para o anúncio voltar na
        # próxima rodada (como no Sundek). Antes virava "sem_evidencia" e não era mais analisado.
        _log(f"{prefix} → ERRO marca: {str(e)[:80]}")
        return {**item, "classificacao": reanalise.erro(reanalise.ETAPA_MARCA, e)}, in_tok, out_tok

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

    # 2b. Fotos para os agentes daqui em diante (classify/orientacao.py, mesmo passo do
    #     Sundek): as giradas ficam em pé e, se as costas só aparecem depois da 5ª foto, essa
    #     foto entra como 6ª (14/11/2026: anúncio de 11 fotos com as costas na 9 e na 11
    #     saía como "sem foto do bolso"). Só roda em quem já passou por short + Ville.
    item, u = orientacao.para_agentes(item)
    if u:
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("orientacao", u.get("model") or "", u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        if orientacao.girou(item):
            prefix += f" [{orientacao.resumo(item)}]"

    # 3. Tartaruga (padrão de estampa)
    try:
        tartaruga = classificar_tartaruga(item)
        u = tartaruga.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("tartaruga", u.get("model") or IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    except Exception as e:
        # Idem: sem a resposta do padrão o anúncio não tem veredito. Antes saía "indefinido" e
        # podia ir para o app com o aviso "a IA não identificou o padrão".
        _log(f"{prefix} → ERRO padrão: {str(e)[:80]}")
        return {**item, "marca_check": marca, "classificacao": reanalise.erro("tartaruga", e)}, in_tok, out_tok

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
    # Liso fora das ofertas (config.VILLE_LISO_OFERTA): mesmo atalho do "outro".
    if tipo_tart == "liso" and not VILLE_LISO_OFERTA:
        _log(f"{prefix} → {tag_tart} — liso fora do foco, pula atributos")
        return {**item, "marca_check": marca, "tartaruga": tartaruga,
                "classificacao": {"tipo": "liso", "autenticidade": "indefinido"}}, in_tok, out_tok

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
            _track("autenticidade", u.get("model") or IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        except Exception as e:
            # Idem: o teste do bolso é o filtro de falsos. Antes a falha virava "indefinido" e
            # o anúncio passava só com o aviso "a IA não conseguiu confirmar".
            _log(f"{prefix} → ERRO autenticidade: {str(e)[:80]}")
            return {**item, "marca_check": marca, "tartaruga": tartaruga,
                    "classificacao": reanalise.erro("autenticidade", e)}, in_tok, out_tok

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

    # 4. Cor de FUNDO (sempre — Ville não tem critério de listras). Agente próprio da Ville
    #    (o do Sundek lia azul claríssimo como branco e não marcava multicolor/neon).
    try:
        cor = classificar_cor_fundo(item)
        u = cor.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("cor", u.get("model") or IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        u2 = u.get("segunda_olhada") or {}
        if u2:  # Haiku conferindo um "branco"
            _track("cor_branco", u2.get("model") or "anthropic/claude-haiku-5.5",
                   u2.get("prompt_tokens", 0), u2.get("completion_tokens", 0))
        linha += f" | cor={cor.get('cor_principal')}"
    except Exception as e:
        # A cor de fundo decide o descarte do liso e o fecho decide botão/fivela/velcro: sem a
        # resposta, o anúncio volta para a análise em vez de ser pontuado sem ela.
        _log(f"{linha} | ERRO cor: {str(e)[:80]}")
        return {**item, "marca_check": marca, "tartaruga": tartaruga,
                "classificacao": reanalise.erro("cor", e)}, in_tok, out_tok

    # 5. Etiqueta
    try:
        etiqueta = verificar_etiqueta(item)
        u = etiqueta.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("etiqueta", u.get("model") or IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
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
        _track("cordao", u.get("model") or IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
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
        _track("fecho", u.get("model") or IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        tf = fecho.get("tipo_fechamento")
        if tf in ("botao", "fivela", "velcro"):
            linha += f" | fecho={tf}✗"
        elif tf and tf != "indefinido":
            linha += f" | fecho={tf}"
    except Exception as e:
        _log(f"{linha} | ERRO fecho: {str(e)[:80]}")
        return {**item, "marca_check": marca, "tartaruga": tartaruga,
                "classificacao": reanalise.erro("fecho", e)}, in_tok, out_tok

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
    # 8. Conservação (desbotado + mancha → aviso no app), só em quem vai pro app: o score relê.
    #    Fica em "conservacao" — "estado" é o campo do Vinted ("Muy bueno"…).
    if resultado["score"].get("decisao") in ("compravel", "medio"):
        try:
            estado = verificar_estado(resultado)
            for u in estado.pop("_usage", []):
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                _track("estado", u.get("model") or "anthropic/claude-haiku-5.5",
                       u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            resultado["conservacao"] = estado
            if estado.get("desbotado") in ("forte", "talvez"):
                linha += f" | desbotado={estado['desbotado']}"
            if estado.get("mancha"):
                linha += " | mancha"
            resultado["score"] = calcular_score(resultado)
        except Exception as e:  # noqa: BLE001 — sem o estado, o item segue sem aviso
            resultado["conservacao"] = {"desbotado": None, "erro": str(e)[:120]}
    s = resultado["score"]
    linha += f" | {s.get('decisao')} ({s.get('score')})"
    _log(linha)
    return resultado, in_tok, out_tok


# Teto de itens do acervo reanalisados por rodada (ver `rever` no main): ~US$ 0,012 cada e
# o passo Classify Ville tem 15 min.
REVER_TITULO_MAX = 6

# Teto da 2ª olhada do bolso por rodada (classify/bolso_confere.py: ~US$ 0,04 e ~40 s cada; as
# conferências rodam em paralelo). Normal: 0–1 por rodada; na 1ª, os aprovados que já estão no app.
BOLSO_CONFERE_MAX_POR_RODADA = 4

# Anúncios que ficaram sem análise por falha de chamada (ver _falha_ia) voltam para a rodada
# enquanto estão ativos e foram vistos há pouco.
FALHA_IA_HORAS = 48
FALHA_IA_MAX = 60


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
    _reset_cost()  # zera o tracker global antes de acumular o custo REAL por etapa/modelo

    checkpoint_path = DATA / "coleta-ville-classificada.json"
    # acervo_previo = TODOS já vistos (por id), pra acumular no _salvar e não perder
    # itens que sumiram do scrape. ja_processados = subconjunto já classificado, só
    # pra pular quem não precisa reclassificar (espelha o run.py do Sundek).
    acervo_previo: dict[str, dict] = {}
    ja_processados: dict[str, dict] = {}
    if checkpoint_path.exists():
        try:
            for x in json.loads(checkpoint_path.read_text(encoding="utf-8")):
                rid = x.get("id")
                if not rid:
                    continue
                acervo_previo[rid] = x
                if (x.get("classificacao") or {}).get("tipo") is not None and not _falha_ia(x):
                    ja_processados[rid] = x
        except Exception:
            pass
    if acervo_previo:
        print(f"  acervo acumulado: {len(acervo_previo)} itens já conhecidos.")

    # Ativos cortados pela regra antiga do título (só ele, sem IA) que a regra de hoje deixa
    # passar: voltam para a rodada, poucos por vez. Só os vistos desde que a Ville entrou no
    # app (VILLE_APP_DESDE) — os mais velhos nem aparecem lá.
    no_scrape = {x.get("id") for x in itens}
    rever = [x for rid, x in acervo_previo.items()
             if rid not in no_scrape and x.get("status") == "ativo"
             and (x.get("classificacao") or {}).get("motivo") == "titulo sem Vilebrequin"
             and (x.get("primeiro_visto") or "") >= VILLE_APP_DESDE
             and _parece_ville(x)[0]][:REVER_TITULO_MAX]
    if rever:
        print(f"  {len(rever)} cortados só pelo título (marca Vilebrequin no Vinted) — analisando de novo.")
        for x in rever:
            ja_processados.pop(x.get("id"), None)
        # Sem o score velho ("nao_ville"): as saídas antecipadas do _processar (padrão
        # "outro", tamanho…) não calculam score, e o pass final só calcula quem não tem.
        rever = [{k: v for k, v in x.items() if k != "score"} for x in rever]
        itens = itens + rever
        total = len(itens)

    # Falha de chamada nas últimas 48 h: o anúncio só voltava enquanto estivesse entre os 20
    # mais novos do scrape. Os ativos entram de novo, até 60 por rodada (mesma regra do Sundek).
    desde_falha = (datetime.now(timezone.utc) - timedelta(hours=FALHA_IA_HORAS)).isoformat()
    com_falha = [x for rid, x in acervo_previo.items()
                 if rid not in no_scrape and x.get("status") == "ativo" and _falha_ia(x)
                 and (x.get("primeiro_visto") or "") >= desde_falha
                 and not reanalise.em_espera(x)][:FALHA_IA_MAX]
    if com_falha:
        print(f"  {len(com_falha)} itens com falha de IA nas últimas {FALHA_IA_HORAS} h — tentando de novo.")
        # sem o que a tentativa anterior gravou: as saídas antecipadas do _processar não recalculam
        itens = itens + [{k: v for k, v in x.items() if k not in reanalise.CAMPOS_DA_IA}
                         for x in com_falha]
        total = len(itens)

    # Reanálise pedida à mão (data/reanalise_pedida.json): uma vez por anúncio e por carimbo.
    pedidos = reanalise.pendentes("ville", acervo_previo)
    if pedidos:
        print(f"  {len(pedidos)} anúncio(s) com reanálise pedida — entrando na rodada.")
        for rid in pedidos:
            ja_processados.pop(rid, None)
        itens = reanalise.juntar(itens, pedidos)
        total = len(itens)

    # Quem falhou numa etapa do meio há pouco espera a vez: cada volta paga de novo a marca e
    # o padrão (gpt-4o) antes de chegar à etapa que falhou (classify/reanalise.py).
    aguardando = {item.get("id") for item in itens
                  if item.get("id") not in pedidos and reanalise.em_espera(acervo_previo.get(item.get("id")))}
    pendentes = [(i, item) for i, item in enumerate(itens)
                 if item.get("id") not in ja_processados and item.get("id") not in aguardando]
    pulados = total - len(pendentes) - len(aguardando)
    if pulados:
        print(f"  {pulados} itens já classificados — pulando. {len(pendentes)} pendentes.\n")
    if aguardando:
        print(f"  {len(aguardando)} itens com falha de IA há pouco — aguardando a próxima tentativa.")

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
            resultado = reanalise.anotar_falha(resultado, acervo_previo.get(resultado.get("id")))
            resultados.append((orig_i, resultado))
            with _counters_lock:
                input_tokens += in_t
                output_tokens += out_t
                concluidos += 1
                if concluidos % 10 == 0:
                    _salvar(resultados, itens, acervo_previo, checkpoint_path)

    _salvar(resultados, itens, acervo_previo, checkpoint_path)

    # Pass final: garante que TODO item tenha score (inclusive os cacheados de
    # rodadas antigas, que foram pulados e podem não ter passado pelo score_ville).
    out = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    mudou = False
    for x in out:
        if "score" not in x and (x.get("classificacao") or {}).get("tipo"):
            x["score"] = calcular_score(x)
            mudou = True
        # "indefinido" com 2 de 3 leituras vendo corte no bolso é suspeita, não "não deu para
        # ver": acerta o que foi gravado antes de 18/11/2026 e refaz o score (trava em médio).
        if acertar_gravado(x):
            x["score"] = calcular_score(x)
            mudou = True
        # Liso aprovado antes de sair das ofertas (config.VILLE_LISO_OFERTA): refaz o score, que
        # agora descarta — senão ficaria no app, porque este passe só calcula quem não tem score.
        elif (not VILLE_LISO_OFERTA and (x.get("classificacao") or {}).get("tipo") == "liso"
              and (x.get("score") or {}).get("decisao") in ("compravel", "medio")):
            x["score"] = calcular_score(x)
            mudou = True
    # 2ª olhada do bolso nos aprovados "original" (classify/bolso_confere.py, 20/11/2026): recortes
    # por borda, exemplos marcados, 3 leituras. 2+ vendo o bolso não casar → suspeito (só aviso).
    alvos = [x for x in out if precisa_conferir_bolso(x)][:BOLSO_CONFERE_MAX_POR_RODADA]
    if alvos:
        with ThreadPoolExecutor(max_workers=len(alvos)) as pool:
            conferidos = list(pool.map(conferir_bolso, alvos))
        for x, chk in zip(alvos, conferidos):
            if chk is None:  # sem rota/falhou → tenta de novo na próxima rodada
                continue
            for u in chk.pop("_usage", []):
                _track("bolso_confere", u.get("model") or "", u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            x["autenticidade"] = {**x["autenticidade"], "confere": chk}
            x["score"] = calcular_score(x)
            mudou = True
            if (chk.get("nao_casa") or 0) >= 2:
                _log(f"  bolso a conferir: {x.get('id')} {x.get('preco')} — {'; '.join(chk.get('pontos') or [])[:120]}")
        print(f"  bolso 2ª olhada: {len(alvos)} aprovado(s) conferido(s) de perto")
    if mudou:
        checkpoint_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    cnt = lambda t: sum(1 for x in out if (x.get("classificacao") or {}).get("tipo") == t)
    dec = lambda d: sum(1 for x in out if (x.get("score") or {}).get("decisao") == d)

    # Custo REAL por etapa/modelo (o cost_tracker registrou marca/tartaruga/autenticidade/
    # fecho como gpt-4o e cor/etiqueta/cordão como mini). Antes o custo era PISO — tudo
    # precificado como mini, subestimando ~5-10x o gasto das etapas gpt-4o.
    por_etapa = _dump_cost()  # {etapa: {modelo: {in, out, calls}}}
    total_usd = 0.0
    for etapa_d in por_etapa.values():
        for modelo, d in etapa_d.items():
            p = _PRECOS.get(modelo, {"in": 0.0, "out": 0.0})
            total_usd += (d["in"] / 1_000_000) * p["in"] + (d["out"] / 1_000_000) * p["out"]

    # Persiste o custo deste run pro histórico/relatório. Formato igual ao
    # custo_por_etapa.json do Sundek (por_etapa → modelo), pra o history.py aplicar
    # o preço certo por modelo. duracao_s/itens ficam ao lado, fora do por_etapa.
    try:
        (DATA / "custo_ville.json").write_text(json.dumps({
            "por_etapa": por_etapa,
            "duracao_s": round(time.time() - t0, 1),
            "itens_processados": len(pendentes),
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
    print(f"  Custo real:        ${total_usd:.5f} (~R$ {total_usd * 5:.3f})  [gpt-4o + mini, por etapa]")
    print(_relatorio_cost(len(pendentes)))
    print(f"  Duração:           {time.time() - t0:.1f}s")
    print(f"\n  Salvo em data/coleta-ville-classificada.json")


if __name__ == "__main__":
    main()
