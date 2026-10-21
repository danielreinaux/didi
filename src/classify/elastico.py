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
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_elastico(item: dict) -> dict:
    """Retorna dict com tem_elastico, evidencia, confianca, _usage."""
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {"tem_elastico": True, "evidencia": "sem fotos", "confianca": 0}

    # Saída SEM os campos pensamento_* (out/2026): o system (com o protocolo e os exemplos)
    # continua igual — e cacheado —, só a resposta encolhe (~226 → ~48 tokens de saída,
    # −US$ 0,0018/chamada). Gabarito: tem_elastico/decisão dentro do ruído do v2 (2 rodadas).
    texto = (prompt.usuario(item.get("titulo") or "") +
             " IMPORTANTE: responda SOMENTE o JSON final com os campos tem_elastico, "
             "tipo_fechamento e evidencia — NÃO escreva os campos pensamento_*.")
    conteudo_usuario = [
        {"type": "text", "text": texto},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_gpt4o()
    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo_usuario},
        ],
        max_tokens=300,  # sem os campos pensamento_* (resposta curta)
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
