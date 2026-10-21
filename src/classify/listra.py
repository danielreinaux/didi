"""Detecta listra Sundek autêntica vs piping via vision dedicada."""
import json
import os

from openai import OpenAI

from ..config import IA, LISTRA_FAIXA_UNICA
from ..utils import llm
from ..prompts import listra_confirma
from ..prompts import listra_sundek as prompt
from ..utils.ratelimit import pace_gpt4o, pace_mini

# Decisão do cliente (out/2026): faixa de UMA cor só na COSTURA LATERAL não conta.
# Arco nas costas de 1 cor segue contando (regra de jun/2026, fora da decisão).
_FORMAS_SEM_LISTRA_SE_1_COR = {"reta_lateral", "borda_perna"}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida. Coloque em .env")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_listra(item: dict) -> dict:
    """Retorna dict com cores, e_piping, e_listra_sundek, bicolor, evidencia."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"cores": [], "e_piping": False, "e_listra_sundek": False,
                "bicolor": False, "evidencia": "sem fotos"}

    # Fotos ROTULADAS ("Foto 1", "Foto 2"...) + protocolo foto a foto: o mini
    # ignorava closes/prints pequenos e fotos giradas onde a listra aparece.
    conteudo = prompt.conteudo_usuario(item.get("titulo") or "", fotos, "low")

    # Roda no MINI: o comparativo de modelos (jul/2026, data/modeltest/4datasets)
    # mostrou o mini EMPATANDO/superando o 4o em Listra e Bicolor — +9pts no Sundek
    # base, empate nos compráveis. Swap sem perda de qualidade e mais barato.
    # (Reverter pra IA["model_detalhes"] + pace_gpt4o se algum dia regredir.)
    pace_mini()
    resp = llm.create(
        "sundek:listra",
        model=IA["model"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=800,  # CoT v2 precisa de mais tokens pros campos pensamento_*
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {"cores": [], "e_piping": False, "e_listra_sundek": False,
                  "bicolor": False, "evidencia": "JSON inválido"}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "model": resp.model,
    }
    return parsed


# ── 2ª olhada: "faixa de uma cor só" (LISTRA_FAIXA_UNICA="nao_conta") ────────────
# O v3 sub-conta cores (lê "amarelo" num arco amarelo-neon + branco; 10 de 77 listras
# reais do gabarito saem com 1 cor), então "1 cor" dele NÃO basta para descartar. Quando
# o v3 diz listra com ≤1 cor, o gpt-4o (detail HIGH) conta as faixinhas e diz onde a
# faixa está. Medido em 47 itens (+3 repetições nos 14 sensíveis): 11/11 faixas de 1 cor
# na lateral pegas, 30/30 listras de 2+ cores preservadas, estável 3/3. Em detail LOW o
# 4o perde o fio azul do 9280883900 (comprável) → HIGH (~US$ 0,0095/chamada).

def modo_faixa_unica() -> str:
    return os.environ.get("LISTRA_FAIXA_UNICA", LISTRA_FAIXA_UNICA)


def precisa_confirmar(tem_listra, cores, ja_confirmado: bool = False) -> bool:
    """True se a regra do cliente está ligada e o v3 disse listra com ≤1 cor."""
    if modo_faixa_unica() != "nao_conta" or tem_listra is not True or ja_confirmado:
        return False
    return len({str(c).strip().lower() for c in (cores or []) if str(c).strip()}) <= 1


def confirmar_faixa_unica(item: dict) -> dict | None:
    """Roda a 2ª olhada. Retorna {"forma", "faixas", "n_cores", "evidencia",
    "rejeitada": bool, "_usage": {...}} ou None se a chamada falhar (mantém o v3)."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return None
    try:
        pace_gpt4o()
        resp = llm.create(
            "sundek:listra_confirma",
            model=IA["model_detalhes"],
            messages=[
                {"role": "system", "content": listra_confirma.SISTEMA},
                {"role": "user", "content": listra_confirma.conteudo_usuario(
                    item.get("titulo") or "", fotos, "high")},
            ],
            max_tokens=400,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        conf = json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None
    try:
        n = int(conf.get("n_cores"))
    except (TypeError, ValueError):
        n = len({str(f).strip().lower() for f in (conf.get("faixas") or [])})
    conf["n_cores"] = n
    conf["rejeitada"] = n <= 1 and conf.get("forma") in _FORMAS_SEM_LISTRA_SE_1_COR
    conf["_usage"] = {
        "model": resp.model,
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return conf
