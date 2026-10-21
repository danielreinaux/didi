"""Cliente de classificação visual (liso/estampado/logo_grande) via OpenAI Vision."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..utils.ratelimit import pace_mini
from ..prompts import liso_vs_estampado as prompt

_client: OpenAI | None = None
_TIPOS = {"liso", "logo_grande", "estampado", "indefinido"}


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida. Coloque em .env")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def classificar_item(item: dict) -> dict:
    # Só as 2 primeiras fotos (out/2026): no mini cada foto low custa ~2.833 tokens; no
    # gabarito tipo/aparência/brilho e a decisão ficaram iguais com 2, 3 e 5 fotos.
    fotos = (item.get("fotos") or [])[:2]
    if not fotos:
        return {"tipo": "indefinido", "justificativa": "sem fotos", "confianca": 0}

    conteudo_usuario = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_mini()
    resp = _get_client().chat.completions.create(
        model=IA["model"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo_usuario},
        ],
        max_tokens=200,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {"tipo": "indefinido", "justificativa": "JSON inválido", "confianca": 0, "raw": texto}

    # tipo fora dos 4 valores (o mini às vezes escreve um campo/critério no lugar do tipo)
    # → deriva das flags, como manda a regra de prioridade do prompt.
    if parsed.get("tipo") not in _TIPOS and "corpo_tem_padrao_repetido" in parsed:
        parsed["tipo_raw"] = parsed.get("tipo")
        parsed["tipo"] = ("estampado" if parsed.get("corpo_tem_padrao_repetido")
                          else "logo_grande" if parsed.get("tem_logo_grande") else "liso")

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
