"""Classifica o TIPO DE FECHO (closure) do short Vilebrequin.

Usado pelo score_ville para EXCLUIR fivela/botão/velcro (decisão do dono 17/06:
só compra cordão/elástico). Roda em gpt-4o (visão fina, igual ao elástico do
Sundek) porque distinguir botão/fivela de ilhó/botão-de-bolso é detalhe sutil
e um erro aqui excluiria um short bom.

Devolve só o tipo cru; a exclusão fica no score_ville.py.
"""
import json
import os

from openai import OpenAI

from ..config import IA
from ..utils import llm
from ..prompts import fecho_ville as prompt
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


def verificar_fecho(item: dict) -> dict:
    """Retorna dict com tipo_fechamento, evidencia, confianca, _usage."""
    # 8 fotos em high (era 4 em low): o cordão/fecho costuma estar numa foto de detalhe e
    # fino demais pra baixa resolução. Gabarito Ville 30/10/2026 → ver config.IA_ROTAS.
    fotos = (item.get("fotos") or [])[:8]
    if not fotos:
        return {
            "tipo_fechamento": "indefinido",
            "evidencia": "sem fotos",
            "confianca": 0,
            "_usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in fotos],
    ]

    if not llm.tem_rota("ville:fecho"):
        pace_gpt4o()
    resp = llm.create(
        "ville:fecho",
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
            "tipo_fechamento": "indefinido",
            "evidencia": "JSON inválido",
            "confianca": 0,
            "raw": texto,
        }

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "model": resp.model,
    }
    return parsed
