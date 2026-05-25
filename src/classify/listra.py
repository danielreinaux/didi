"""Detecta listra Sundek autêntica vs piping via vision dedicada."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import listra_sundek as prompt
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

    # gpt-4o porque a decisão é crítica e o detalhe de listra vs piping é sutil
    pace_gpt4o()
    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],
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
        parsed = {"cores": [], "e_piping": False, "e_listra_sundek": False,
                  "bicolor": False, "evidencia": "JSON inválido"}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
