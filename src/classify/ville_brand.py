"""Verifica se a peça é REALMENTE Vilebrequin E se é original (bolso traseiro)."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import verifica_ville as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    return _client


def verificar_ville(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {
            "e_vilebrequin": "indefinido",
            "e_short": "indefinido",
            "autenticidade": "sem_foto_bolso",
            "bolso_ok": None,
            "evidencia": "sem fotos",
            "confianca": 0,
        }

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "auto"}} for u in fotos],
    ]

    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],  # gpt-4o para visão mais fina (bolso traseiro)
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=250,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {
            "e_vilebrequin": "indefinido",
            "autenticidade": "indefinido",
            "bolso_ok": None,
            "evidencia": "JSON inválido",
            "confianca": 0,
            "raw": texto,
        }

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
