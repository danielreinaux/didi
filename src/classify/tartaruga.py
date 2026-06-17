"""Classifica o padrão de estampa do Vilebrequin: tartaruga_grande, tartaruga_pequena, liso, outro."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import tartaruga as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    return _client


def classificar_tartaruga(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {
            "tipo": "indefinido",
            "cor_principal": None,
            "tartaruga_variedade": None,
            "aparencia": "indefinido",
            "justificativa": "sem fotos",
            "confianca": 0,
        }

    conteudo = list(prompt.referencias_few_shot())  # 1 ref de fundo multicolor pra calibrar
    conteudo.append({"type": "text", "text": prompt.usuario(item.get("titulo") or "")})
    # detail=low: tartaruga grande é fácil de ver em baixa resolução (~10x mais barato).
    conteudo += [{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos]

    resp = _get_client().chat.completions.create(
        # gpt-4o (não mini): a distinção tartaruga × animais parecidos (camaleão,
        # lagarto) exige visão fina — o mini erra mesmo em detail=high. Em detail=low
        # o 4o já acerta (ver teste), então fica barato (~$0.001-0.002/item).
        model=IA["model_detalhes"],
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
            "tipo": "indefinido",
            "cor_principal": None,
            "tartaruga_variedade": None,
            "aparencia": "indefinido",
            "justificativa": "JSON inválido",
            "confianca": 0,
            "raw": texto,
        }

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
