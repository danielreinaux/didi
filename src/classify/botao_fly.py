"""Detector dedicado de BOTÃO/SNAP/VELCRO no fly (roda depois do elástico, só nos
itens que sobreviveram até lá — ou seja, poucos e baratos)."""
import json
import os

from openai import OpenAI

from ..config import IA
from ..prompts import botao_fly as prompt
from ..prompts import velcro_fly as prompt_velcro
from .crop_fly import recortar_fly

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_botao(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"tem_botao": None, "tipo": "indefinido", "evidencia": "sem fotos"}
    cr = recortar_fly(item)
    conteudo = [{"type": "text", "text": prompt.usuario(item.get("titulo") or "")}]
    if cr.get("crop"):
        conteudo.append({"type": "text", "text": "ZOOM da cintura frontal central (topo da braguilha):"})
        conteudo.append({"type": "image_url", "image_url": {"url": cr["crop"], "detail": "high"}})
    if cr.get("foto_frente_url"):
        # a foto de frente inteira em HIGH (resolução nativa): cobre bbox imprecisa do zoom
        conteudo.append({"type": "text", "text": "Foto da FRENTE inteira (alta resolução):"})
        conteudo.append({"type": "image_url", "image_url": {"url": cr["foto_frente_url"], "detail": "high"}})
    conteudo.append({"type": "text", "text": "Fotos gerais (contexto):"})
    conteudo += [{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos]
    resp = _get_client().chat.completions.create(
        model=os.environ.get("BOTAO_MODEL", IA["model_detalhes"]),
        messages=[{"role": "system", "content": prompt.SISTEMA}, {"role": "user", "content": conteudo}],
        max_tokens=300, temperature=0.1, response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {"tem_botao": None, "tipo": "indefinido", "evidencia": "JSON inválido"}
    parsed["_crop_modo"] = cr.get("modo")
    parsed["_crop_foto"] = cr.get("foto_index")
    parsed["_crop"] = cr.get("crop") if (cr.get("crop") or "").startswith("data:") else None
    parsed["_usage"] = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}
    return parsed


def verificar_velcro(item: dict) -> dict:
    """Velcro na braguilha — pros shorts SEM elástico (onde o botao_fly não roda).
    Todas as fotos em detail=low (o velcro aparece em close-up da braguilha aberta,
    tira grande: low basta) → ~US$0,003/item no gpt-4o."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"tem_velcro": None, "evidencia": "sem fotos"}
    conteudo = [{"type": "text", "text": prompt_velcro.usuario(item.get("titulo") or "")}]
    for i, u in enumerate(fotos):
        conteudo.append({"type": "text", "text": f"Foto {i}:"})
        conteudo.append({"type": "image_url", "image_url": {"url": u, "detail": "low"}})
    resp = _get_client().chat.completions.create(
        model=os.environ.get("BOTAO_MODEL", IA["model_detalhes"]),
        messages=[{"role": "system", "content": prompt_velcro.SISTEMA}, {"role": "user", "content": conteudo}],
        max_tokens=250, temperature=0.1, response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {"tem_velcro": None, "evidencia": "JSON inválido"}
    parsed["_usage"] = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}
    return parsed
