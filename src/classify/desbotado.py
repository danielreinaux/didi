"""2º olhar do DESBOTADO: confirma (ou derruba) o "desbotado" que o prompt de tipo deu num LISO.

Por quê: o gpt-4o-mini do tipo marca desbotado com muito falso positivo (no conjunto curado,
15/41 lisos limpos e 14/15 com só marquinhas em close-up), e cada falso desbotado é um
comprável descartado (ex. 9280328167 no gabarito). gpt-4o/4.1-mini/gpt-5.6-luna/Gemini com
o mesmo prompt dedicado continuam marcando as marquinhas de close-up; o Claude Haiku segue
a política do gabarito. Por isso o 2º olhar usa Haiku via OpenRouter, 3 votos (maioria).

Custo: só roda nos lisos que o mini marcou desbotado (~2% dos lisos; ~60-100/mês) ×
3 chamadas × ~US$0,0007 → < US$0,25/mês.

Sem a rota sundek:desbotado ativa (sem OPENROUTER_API_KEY) ou se a API falhar → confirmado=None e o pipeline mantém o
"desbotado" do mini (comportamento antigo, conservador).
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from ..config import IA
from ..prompts import desbotado as prompt
from ..utils import llm

AGENTE = "sundek:desbotado"  # rota em config.IA_ROTAS (Haiku 5.5 via OpenRouter)


def _parse(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto or "", re.S)
    try:
        return json.loads(m.group(0) if m else texto)
    except Exception:
        return {"erro": "JSON inválido", "raw": (texto or "")[:200]}


def _um_voto(conteudo: list) -> dict:
    try:
        # fallback=False: o Haiku só existe no OpenRouter — se a rota falhar, o voto falha
        # (e, sem maioria, quem chama mantém o desbotado do tipo).
        resp = llm.create(
            AGENTE, fallback=False,
            model=IA["model_desbotado"],
            messages=[{"role": "system", "content": prompt.SISTEMA},
                      {"role": "user", "content": conteudo}],
            max_tokens=1500,   # o Haiku 5.5 pode gastar tokens raciocinando antes do JSON
            temperature=0.1,
        )
    except Exception as e:
        return {"erro": str(e)[:120]}
    out = _parse(resp.choices[0].message.content)
    u = resp.usage
    out["_usage"] = {"prompt_tokens": u.prompt_tokens or 0, "completion_tokens": u.completion_tokens or 0,
                     "model": resp.model}
    return out


def confirmar_desbotado(item: dict) -> dict:
    """Retorna {"confirmado": True|False|None, "votos": [...], "motivo": str, "_usage": {...}}.
    confirmado=None → não deu pra checar (sem chave/erro): quem chama mantém o desbotado."""
    rota = llm.tem_rota(AGENTE)
    fotos = (item.get("fotos") or [])[:6]
    if not rota or not fotos:
        return {"confirmado": None, "votos": [], "motivo": "sem rota (OPENROUTER_API_KEY)" if not rota else "sem fotos"}
    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]
    n = int(IA.get("desbotado_votos", 3))
    with ThreadPoolExecutor(n) as ex:
        votos = list(ex.map(lambda _: _um_voto(conteudo), range(n)))
    uso = {"prompt_tokens": sum(v.get("_usage", {}).get("prompt_tokens", 0) for v in votos),
           "completion_tokens": sum(v.get("_usage", {}).get("completion_tokens", 0) for v in votos),
           "model": next((v["_usage"]["model"] for v in votos if v.get("_usage")), IA["model_desbotado"])}
    validos = [v.get("veredito") for v in votos if v.get("veredito") in ("desbotado", "ok")]
    if len(validos) * 2 <= n:   # maioria dos votos falhou → não decide
        return {"confirmado": None, "votos": validos, "motivo": "votos insuficientes", "_usage": uso}
    sim = validos.count("desbotado")
    confirmado = sim * 2 > len(validos)
    # tecido de moletom (cliente: "descartar sempre") — maioria dos votos que responderam
    tecidos = [v.get("tecido") for v in votos if v.get("tecido") in ("banho", "moletom")]
    moletom = bool(tecidos) and tecidos.count("moletom") * 2 > len(tecidos)
    ref = next((v for v in votos if v.get("veredito") == ("desbotado" if confirmado else "ok")), {})
    motivo = "; ".join(f"{k}: {ref.get(k)}" for k in ("cor_gasta", "manchas", "desgaste_fisico")
                       if ref.get(k) and str(ref.get(k)).lower() not in ("não", "nao"))
    return {"confirmado": confirmado, "votos": validos, "motivo": motivo[:300], "moletom": moletom, "_usage": uso}


def aplicar(c: dict, item: dict) -> dict | None:
    """Se o tipo marcou LISO/indefinido como desbotado, roda o 2º olhar e, se ele derrubar,
    volta aparencia para "ok" (guarda o voto do mini em aparencia_mini). Retorna o check
    (para log/custo) ou None se não precisou rodar."""
    if c.get("aparencia") != "desbotado" or c.get("tipo") not in ("liso", "indefinido", None):
        return None
    chk = confirmar_desbotado(item)
    c["desbotado_check"] = {k: chk.get(k) for k in ("confirmado", "votos", "motivo", "moletom")}
    if chk.get("confirmado") is False:
        c["aparencia_mini"] = "desbotado"
        c["aparencia"] = "ok"
    return chk


def precisa_checar_aprovado(it: dict) -> bool:
    """LISO ativo que vai PASSAR (comprável/barganha) e nunca teve o 2º olhar. O modelo de tipo
    do OpenRouter (gemma-4) marca bem menos "desbotado" que o gpt-4o-mini: em 21/10, dos 68
    lisos que o mini tinha descartado por desbotado, o gemma marcou só 2 — e 3 dos 9 que
    voltariam a passar eram rosa desbotado / moletom. Por isso o Haiku confere TODO liso que
    vai aparecer no app, não só os que o tipo desconfiou."""
    cl = it.get("classificacao") or {}
    return ((it.get("score") or {}).get("decisao") in ("compravel", "medio")
            and (it.get("status") or "ativo") == "ativo"
            and cl.get("tipo") == "liso" and "desbotado_check" not in cl)


def checar_aprovado(it: dict) -> dict | None:
    """Roda o 2º olhar num liso aprovado e aplica: desbotado → tipo "desbotado"; moletom →
    "nao_short". Retorna o check (p/ custo) ou None se não deu pra checar (tenta na próxima
    rodada). Quem chama recalcula o score."""
    chk = confirmar_desbotado(it)
    if chk.get("confirmado") is None:
        return None
    cl = it["classificacao"]
    cl["desbotado_check"] = {k: chk.get(k) for k in ("confirmado", "votos", "motivo", "moletom")}
    if chk["confirmado"]:
        cl["tipo_original"] = cl.get("tipo")
        cl["aparencia"] = "desbotado"
        cl["tipo"] = "desbotado"
    elif chk.get("moletom"):
        cl["tipo_original"] = cl.get("tipo")
        cl["tipo"] = "nao_short"
        cl["motivo_nao_short"] = "short de moletom (2º olhar)"
    return chk
