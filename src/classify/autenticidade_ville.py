"""Verifica autenticidade do Vilebrequin via zoom no bolso traseiro.

Único critério: o padrão da estampa continua dentro do bolso traseiro?
- continua → original
- bolso liso/cortado → falso
- short liso → indefinido
- sem foto do bolso → sem_foto_bolso

Usa o mesmo recortador do Sundek (crop_bolso) — manda zoom HIGH + fotos
gerais LOW pro gpt-4o. Custo médio: ~$0.03/item.
"""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import autenticidade_ville as prompt
from ..utils.ratelimit import pace_gpt4o
from .crop_bolso import recortar_bolso

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=8)
    return _client


def verificar_autenticidade(item: dict) -> dict:
    """Retorna dict com autenticidade, evidencia, _usage."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {
            "autenticidade": "sem_foto_bolso",
            "evidencia": "sem fotos",
            "_usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    # Zoom no bolso traseiro (mesmo pipeline do Sundek)
    crop_info = recortar_bolso(item)
    crop_url = crop_info.get("crop")

    conteudo = [{"type": "text", "text": prompt.usuario(item.get("titulo") or "")}]
    if crop_url:
        conteudo.append({"type": "text", "text": "ZOOM do bolso traseiro (use esta pra ver se o padrão continua):"})
        conteudo.append({"type": "image_url", "image_url": {"url": crop_url, "detail": "high"}})
        conteudo.append({"type": "text", "text": "Fotos gerais do short (contexto):"})
    # Fotos gerais em LOW — só servem de contexto; o zoom é onde está a informação.
    conteudo += [{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos]

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
        parsed = {
            "autenticidade": "indefinido",
            "evidencia": "JSON inválido",
        }

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
