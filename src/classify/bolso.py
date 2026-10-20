"""Detecta bolso traseiro Sundek (existe? tem nome SUNDEK?) via vision dedicada."""
import json
import os

from openai import OpenAI

from ..config import IA
from .crop_bolso import recortar_bolso
from ..prompts import bolso_traseiro as prompt
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


# Fallback só com termos inequívocos (ex.: "preto com sol amarelo" NÃO pode disparar).
_FLUO_KW = ("fluo", "neon", "verde-lima", "verde lima", "amarelo-limão", "amarelo limão")


def _patch_fluo(parsed: dict) -> bool:
    if parsed.get("patch_fluo") is True:
        return True
    cor = (parsed.get("cor_patch") or "").lower()
    return any(k in cor for k in _FLUO_KW)


def verificar_bolso(item: dict) -> dict:
    """Retorna dict com tem_bolso, tem_nome, bolso_frontal, evidencia."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"tem_bolso": None, "tem_nome": None, "bolso_frontal": False, "evidencia": "sem fotos"}

    # Recorta e amplia o bolso traseiro — o patch é minúsculo na foto inteira,
    # então mandamos um zoom dedicado pro modelo conseguir ler o texto.
    crop_info = recortar_bolso(item, alvo="patch")
    crop_url = crop_info.get("crop")

    conteudo = [{"type": "text", "text": prompt.usuario(item.get("titulo") or "")}]
    if crop_url and crop_info.get("alvo") == "patch":
        onde = crop_info.get("onde") or "?"
        conteudo.append({"type": "text", "text": (
            f"ZOOM do PATCH (o localizador diz que ele está em: {onde}). Use este zoom para "
            "LER o patch; confirme nas fotos gerais se ele está mesmo no bolso TRASEIRO "
            "(costas) — se estiver num bolso lateral/cargo, isso NÃO é bolso traseiro:")})
        conteudo.append({"type": "image_url", "image_url": {"url": crop_url, "detail": "high"}})
        conteudo.append({"type": "text", "text": "Fotos gerais do short (contexto):"})
    elif crop_url:
        conteudo.append({"type": "text", "text": "ZOOM do bolso traseiro (use esta para ler o patch):"})
        conteudo.append({"type": "image_url", "image_url": {"url": crop_url, "detail": "high"}})
        conteudo.append({"type": "text", "text": "Fotos gerais do short (contexto):"})
    # Fotos gerais em LOW (só contexto). O ZOOM acima é high — quem importa pra ler o patch.
    # Teste em 15 itens: 93% concordância e -47% no custo do bolso.
    conteudo += [{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos]

    # gpt-4o porque a decisão é crítica para exclusão e o detalhe do patch é sutil
    pace_gpt4o()
    resp = _get_client().chat.completions.create(
        model=IA["model_detalhes"],
        messages=[
            {"role": "system", "content": prompt.SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=800,  # CoT v2 precisa de mais tokens pros campos pensamento_*
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    texto = (resp.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(texto)
    except json.JSONDecodeError:
        parsed = {"tem_bolso": None, "tem_nome": None, "bolso_frontal": False, "evidencia": "JSON inválido"}

    # Caso especial (feedback do cliente): patch FLUO (amarelo/lima/rosa/laranja neon)
    # = coleção atual, nome SUNDEK bordado tom sobre tom → invisível na foto. O modelo
    # tende a dizer "só ícone" → exclusão errada (bolso_so_logo). Regra determinística:
    # patch fluo nunca vira "sem nome".
    if parsed.get("tem_bolso") is True and parsed.get("tem_nome") is False and _patch_fluo(parsed):
        parsed["tem_nome"] = True
        parsed["tem_nome_override"] = "patch_fluo"
        parsed["evidencia"] = "[patch fluo → nome tom-sobre-tom presumido] " + (parsed.get("evidencia") or "")

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }
    return parsed
