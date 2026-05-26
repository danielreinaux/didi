"""Detecta se o short tem elástico no cós via vision."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import elastico as prompt
from ..utils.ratelimit import pace_gpt4o

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida. Coloque em .env")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=8)
    return _client


def verificar_elastico(item: dict) -> dict:
    """Retorna dict com tem_elastico, evidencia, confianca, _usage."""
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {"tem_elastico": True, "evidencia": "sem fotos", "confianca": 0}

    conteudo_usuario = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_gpt4o()
    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo_usuario},
        ],
        max_tokens=800,  # CoT v2 precisa de mais tokens pros campos pensamento_*
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {"tem_elastico": True, "evidencia": "JSON inválido", "confianca": 0}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
