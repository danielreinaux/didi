"""Cor de FUNDO do short Vilebrequin (substitui o agente de cor do Sundek na Ville).

Devolve `cor_principal` no mesmo formato que o resto da Ville já lê (classify/cor_ville.py faz
a faixa). Neon/metálico entram no nome ("amarelo neon") para o bucket_cor penalizar.
Gabarito Ville 30/10/2026 (76 itens com faixa de cor): agente do Sundek 88% → este prompt 91%
nas 2 rodadas, mesmo modelo (gpt-4o-mini, 4 fotos em low) e mesmo custo (~US$0,0014/item).
Gemini 3.5 Flash-Lite, Haiku 5.5, gpt-4o e gpt-6.1-sol ficaram em 84–89% com este prompt.
"""
import json

from ..config import IA
from ..prompts import cor_fundo_ville as prompt
from ..utils import llm
from ..utils.ratelimit import pace_mini


def classificar_cor_fundo(item: dict) -> dict:
    """Retorna cor_principal (nome do vocabulário + 'neon'/'metálico'), cor_fundo, neon,
    metalico, evidencia, confianca, _usage."""
    fotos = (item.get("fotos") or [])[:4]
    if not fotos:
        return {"cor_principal": None, "evidencia": "sem fotos", "confianca": 0,
                "_usage": {"prompt_tokens": 0, "completion_tokens": 0}}
    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "low"}} for u in fotos],
    ]
    if not llm.tem_rota("ville:cor_fundo"):
        pace_mini()
    resp = llm.create(
        "ville:cor_fundo",
        model=IA["model"],
        messages=[{"role": "system", "content": prompt.SISTEMA}, {"role": "user", "content": conteudo}],
        max_tokens=250,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    try:
        r = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        r = {}
    uso = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens,
           "model": resp.model}
    # "branco" põe o short na faixa preferida (as faixas de preço mais altas) e o mini lê azul
    # claríssimo como branco (cv02, cv21 do gabarito). Segunda olhada do Haiku 5.5 em high/8 fotos,
    # que separou os 3 brancos verdadeiros dos 2 azul-claríssimo. Só roda no "branco" (~5%).
    if (r.get("cor_fundo") or "").strip().lower() == "branco":
        conf = _segunda_olhada_branco(item)
        if conf and conf.get("cor_fundo"):
            r = {**conf, "evidencia": f"2ª olhada: {conf.get('evidencia') or ''}"}
            uso = {**uso, "segunda_olhada": conf.pop("_usage", None)}
    nome = (r.get("cor_fundo") or "").strip().lower() or None
    principal = nome
    if nome and r.get("neon") is True:
        principal += " neon"
    if nome and r.get("metalico") is True:
        principal += " metálico"
    return {
        "cor_principal": principal,
        "cor_fundo": nome,
        "neon": r.get("neon"),
        "metalico": r.get("metalico"),
        "evidencia": (r.get("evidencia") or "")[:300],
        "confianca": r.get("confianca"),
        "_usage": uso,
    }


def _segunda_olhada_branco(item: dict) -> dict | None:
    fotos = (item.get("fotos") or [])[:8]
    conteudo = [
        {"type": "text", "text": prompt.usuario(item.get("titulo") or "") +
         " Atenção: compare o fundo com o forro de tela/etiqueta brancos antes de dizer branco."},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in fotos],
    ]
    try:
        resp = llm.create(
            "ville:cor_fundo_branco",
            model=IA["model"],
            messages=[{"role": "system", "content": prompt.SISTEMA}, {"role": "user", "content": conteudo}],
            max_tokens=250,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        r = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — sem a 2ª olhada, fica a resposta do mini
        return None
    r["_usage"] = {"prompt_tokens": resp.usage.prompt_tokens,
                   "completion_tokens": resp.usage.completion_tokens, "model": resp.model}
    return r
