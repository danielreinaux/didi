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
from ..prompts import autenticidade_ville as prompt  # noqa: F401  (v1, referência)
from ..prompts import autenticidade_ville_v2 as prompt_v2
from ..utils import llm
from ..utils.ratelimit import pace_gpt4o

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_autenticidade(item: dict) -> dict:
    """Retorna dict com autenticidade, sinal, foto_bolso, evidencia, _usage.

    v2 (02/11/2026): critério do comprador — o bolso traseiro "completa" a estampa? estampado
    sem bolso? etiquetinha interna clonada 00.001.4_8.778? — com as fotos INTEIRAS em high (o
    recorte do bolso errava o lugar em ~metade dos anúncios). gpt-6.1-sol (config.IA_OPENAI).
    Bancada (gabarito Ville + 2 falsos do painel, 79 itens): falsos pegos 0/4 → 5/7, originais
    acusados 0/53, acerto geral 85% → 95%. O v1 (bolso recortado) fica em prompts/autenticidade_ville.py.
    """
    fotos = (item.get("fotos") or [])[:8]
    if not fotos:
        return {
            "autenticidade": "sem_foto_bolso",
            "evidencia": "sem fotos",
            "_usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
    conteudo = [
        {"type": "text", "text": prompt_v2.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in fotos],
    ]
    if not llm.tem_rota("ville:autenticidade"):
        pace_gpt4o()
    resp = llm.create(
        "ville:autenticidade",
        model=IA["model_detalhes"],
        messages=[
            {"role": "system", "content": prompt_v2.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=400,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads((resp.choices[0].message.content or "{}").strip())
    except json.JSONDecodeError:
        parsed = {"autenticidade": "indefinido", "evidencia": "JSON inválido"}
    if parsed.get("autenticidade") not in ("original", "falso", "sem_foto_bolso", "indefinido"):
        parsed["autenticidade"] = "indefinido"
    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "model": resp.model,
    }
    return parsed
