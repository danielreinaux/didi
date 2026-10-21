"""Classificador de cor (tier muito_boa/boa/ok/ruim). Roda só sobre lisos."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..utils.ratelimit import pace_mini
from ..prompts import cor_tier as prompt

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


_TIERS = ("maravilhoso", "muito_boa", "boa", "ok", "ruim")
_NAVY = ("marinho", "navy", "azul escuro", "petróleo escuro", "petroleo escuro")
_ROSA = ("rosa", "pink", "fucsia", "fúcsia", "fuchsia", "magenta")
# Cliente (/decisoes, 21/10/2026): roxo/violeta = ruim; laranja salmão pode ser bem classificada.
_ROXO = ("roxo", "violeta", "lilás", "lilas", "púrpura", "purpura", "purple", "lavanda")
_SALMAO = ("salmão", "salmao", "salmon")
_METAL = ("metál", "metal", "cetim", "espelh", "wet look", "alumínio", "aluminio", "prate")


def _normalizar_tier(parsed: dict) -> dict:
    """Mesma cor → mesmo tier (o mini oscila o tier com o MESMO nome de cor).
    Regras do cliente/gabarito, só sobre o nome que o próprio modelo deu:
      - navy / azul escuro / marinho → maravilhoso (manual: "melhores: azul escuro";
        o mini dava muito_boa/boa pra "azul escuro" em ~1/3 das vezes);
      - azul royal → boa (royal não é navy; gabarito nunca deu royal maravilhoso);
      - cinza claro → boa (cliente: "cinzas são melhores se forem mais escuros");
      - rosa choque / pink / fucsia "ruim" → ok (manual: rosa choque é aceitável),
        exceto se a justificativa for brilho metálico/cetim.
    Guarda o tier original em `tier_modelo`."""
    tier = parsed.get("tier")
    if tier not in _TIERS:
        return parsed
    nome = (parsed.get("cor_principal") or "").lower()
    just = (parsed.get("justificativa") or "").lower()
    novo = tier
    if any(k in nome for k in _NAVY) and tier in ("muito_boa", "boa"):
        novo = "maravilhoso"
    elif "royal" in nome and tier in ("maravilhoso", "muito_boa"):
        novo = "boa"
    elif "cinza claro" in nome and tier in ("muito_boa", "ok"):
        novo = "boa"
    elif any(k in nome for k in _ROXO) and tier != "ruim":
        novo = "ruim"
    elif any(k in nome for k in _SALMAO) and tier in ("ruim", "ok"):
        novo = "boa"
    elif tier == "ruim" and any(k in nome for k in _ROSA) and not any(k in just for k in _METAL):
        novo = "ok"
    if novo != tier:
        parsed["tier_modelo"] = tier
        parsed["tier"] = novo
    return parsed


def classificar_cor(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {"tier": "indefinido", "justificativa": "sem fotos", "confianca": 0}

    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "", item.get("cor"))},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]

    pace_mini()
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
    parsed = _normalizar_tier(parsed)

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
