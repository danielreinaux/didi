"""Detecta listra Sundek autêntica vs piping via vision dedicada."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import listra_sundek as prompt
from ..utils.ratelimit import pace_mini

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

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    # Roda no MINI: o comparativo de modelos (jul/2026, data/modeltest/4datasets)
    # mostrou o mini EMPATANDO/superando o 4o em Listra e Bicolor — +9pts no Sundek
    # base, empate nos compráveis. Swap sem perda de qualidade e mais barato.
    # (Reverter pra IA["model_detalhes"] + pace_gpt4o se algum dia regredir.)
    pace_mini()
    resp = _get_client().chat.completions.create(
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
    }
    return parsed
