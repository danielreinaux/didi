"""Classificador de cor (tier muito_boa/boa/ok/ruim). Roda só sobre lisos."""
import json
import os

from openai import OpenAI

from .config import IA
from .prompts import cor_tier as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def classificar_cor(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {"tier": "indefinido", "justificativa": "sem fotos", "confianca": 0}

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "", item.get("cor"))},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

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
        parsed = {"tier": "indefinido", "justificativa": "JSON inválido", "confianca": 0, "raw": texto}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
