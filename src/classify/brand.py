"""Verifica se a peça é REALMENTE Sundek E se é um SHORT (não sunga)."""
import json
import os
import re

from openai import OpenAI

from ..config import IA
from ..prompts import verifica_sundek as prompt
from ..utils.ratelimit import pace_gpt4o, pace_mini
from ._colagem import colagem

_client: OpenAI | None = None

# Typos de OCR + linhas/slogans da própria Sundek (não são "outra marca").
SUNDEK_ALIASES = {
    "sunder", "sundeck", "sundek.", "sundek,", "sundk",
    "sndk", "sndk58", "sndk 58", "follow the sun", "sundex",
}
# marca_identificada "vazia": o modelo disse nao_sundek SEM ver outra marca.
_SEM_MARCA = {"", "null", "none", "nenhuma", "nenhum", "n/a", "na", "desconhecida", "indefinida", "-"}
# Título com cara de Sundek (typos de vendedor): sandek, sudek, sundeck, sundex, sndk...
_TITULO_SUNDEK = re.compile(r"\bs[ua]n?dec?k|\bsundex|\bsndk", re.I)


def motivo_recheck(item: dict, marca: dict) -> str | None:
    """Quando o mini disse "nao_sundek", decide se vale re-verificar com gpt-4o (detail=high).

    - "titulo": título contém "sundek" (regra antiga) → aceita o 4o se ele NÃO disser "nao".
    - "sem_marca": o mini disse nao_sundek SEM identificar outra marca (não viu o logo do
      sol em detail=low) ou o título tem typo de Sundek → aceita o 4o só se disser "sim"
      (sem evidência nenhuma continua barrado — não abre a porta para short genérico).
    """
    if marca.get("e_sundek") != "nao":
        return None
    titulo = (item.get("titulo") or "").lower()
    if "sundek" in titulo:
        return "titulo"
    mi = str(marca.get("marca_identificada") or "").strip().lower()
    if mi in _SEM_MARCA or _TITULO_SUNDEK.search(titulo):
        return "sem_marca"
    return None


def aceita_recheck(motivo: str, marca_4o: dict) -> bool:
    if motivo == "titulo":
        return marca_4o.get("e_sundek") != "nao"
    return marca_4o.get("e_sundek") == "sim"


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não definida")
    _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


def verificar_sundek(item: dict, model: str | None = None) -> dict:
    fotos = (item.get("fotos") or [])[:5]
    if not fotos:
        return {"e_sundek": "indefinido", "evidencia": "sem fotos", "confianca": 0}

    # detail=low é suficiente pro brand (só precisa ver logo/etiqueta).
    # 'auto' no mini virava 'high' (~25K tokens/foto) — gastava 60% do custo total!
    # detail=high só pro double-check com gpt-4o (raros casos suspeitos).
    detail = "high" if model == IA["model_detalhes"] else "low"
    # No mini (detail=low) as fotos vão numa COLAGEM só (~2.833 tokens no total em vez de
    # ~2.833 por foto): mesmo acerto no gabarito e −2/3 do custo da etapa. O recheck 4o
    # (detail=high) continua com as fotos inteiras.
    imagens = fotos
    if detail == "low" and len(fotos) > 1:
        c = colagem(fotos)
        if c:
            imagens = [c]
    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": detail}} for u in imagens],
    ]

    if (model or IA["model"]) == IA["model_detalhes"]:
        pace_gpt4o()  # só o double-check usa gpt-4o
    else:
        pace_mini()
    resp = _get_client().chat.completions.create(
        model=model or IA["model"],
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
        parsed = {"e_sundek": "indefinido", "evidencia": "JSON inválido", "confianca": 0, "raw": texto}

    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }

    # corrigir falsos negativos por OCR de baixa resolução
    # ex: "Sunder", "Sundeck", "Sundek." lidos como outra marca — e linhas/slogans
    # da PRÓPRIA Sundek que o mini devolve como "outra marca" (SNDK, slogans).
    # Goldenwave NÃO é apelido: o cliente não compra a linha premium (20/10/2026).
    marca_id = (parsed.get("marca_identificada") or "").lower().strip()
    if parsed.get("e_sundek") == "nao" and marca_id in SUNDEK_ALIASES:
        parsed["e_sundek"] = "sim"
        parsed["marca_identificada"] = None
        parsed["evidencia"] = f"[corrigido: '{marca_id}' → Sundek] " + (parsed.get("evidencia") or "")

    return parsed
