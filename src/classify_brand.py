"""Verifica se a peça é REALMENTE Sundek E se é um SHORT (não sunga)."""
import json
import os

from openai import OpenAI

from .config import IA
from .prompts import verifica_sundek as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def verificar_sundek(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:5]
    if not fotos:
        return {"e_sundek": "indefinido", "evidencia": "sem fotos", "confianca": 0}

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "auto"}} for u in fotos],
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
        parsed = {"e_sundek": "indefinido", "evidencia": "JSON inválido", "confianca": 0, "raw": texto}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }

    # corrigir falsos negativos por OCR de baixa resolução
    # ex: "Sunder", "Sundeck", "Sundek." lidos como outra marca
    marca_id = (parsed.get("marca_identificada") or "").lower().strip()
    SUNDEK_TYPOS = {"sunder", "sundeck", "sundek.", "sundek,", "sundk", "sundeck"}
    if parsed.get("e_sundek") == "nao" and marca_id in SUNDEK_TYPOS:
        parsed["e_sundek"] = "sim"
        parsed["marca_identificada"] = None
        parsed["evidencia"] = f"[corrigido: '{marca_id}' → Sundek] " + (parsed.get("evidencia") or "")

    return parsed
