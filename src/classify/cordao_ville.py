"""Classifica a cor do cordão (drawstring) do short Vilebrequin.

Usado pelo score_ville para detectar coleção antiga (cordão cinza).
Roda em gpt-4o-mini (custo baixo) e devolve só a cor — a derivação
'antiga vs atual' e a penalidade ficam no score_ville.py.
"""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import cordao_ville as prompt
from ..utils.ratelimit import pace_mini

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_cordao(item: dict) -> dict:
    """Retorna dict com cordao_cor, evidencia, confianca, _usage."""
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {
            "cordao_cor": "indefinido",
            "evidencia": "sem fotos",
            "confianca": 0,
            "_usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_mini()
    resp = _get_client().chat.completions.create(
        model=IA["model"],
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
        parsed = {
            "cordao_cor": "indefinido",
            "evidencia": "JSON inválido",
            "confianca": 0,
            "raw": texto,
        }

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
