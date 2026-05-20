"""Detecta bolso traseiro Sundek (existe? tem nome SUNDEK?) via vision dedicada."""
import json
import os

from openai import OpenAI

from .config import IA
from .prompts import bolso_traseiro as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida. Coloque em .env")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def verificar_bolso(item: dict) -> dict:
    """Retorna dict com tem_bolso (true/false/null), tem_nome (true/false/null), evidencia."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"tem_bolso": None, "tem_nome": None, "evidencia": "sem fotos"}

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    # gpt-4o porque a decisão é crítica para exclusão e o detalhe do patch é sutil
    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=150,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {"tem_bolso": None, "tem_nome": None, "evidencia": "JSON inválido"}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
