"""Short premiado: o anúncio é um dos 3 modelos favoritos do cliente? (pedido de 27/10/2026)

Só olha quem já PASSOU nas regras normais (comprável), com elástico, cor do corpo escura e que
vai aparecer no app — poucos por dia. O resultado fica em item["premiado"] (uma vez por
item; fotos novas = item reclassificado do zero = olha de novo). O app e o e-mail destacam:
  preço do anúncio ≤ config.PREMIADO_URGENTE_ATE → "🚨 COMPRA URGENTE"; acima → "⭐ disponível".
"""
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import IA
from ..utils import llm
from ..prompts import premiado as prompt

REFS = Path(__file__).resolve().parent.parent / "prompts" / "refs" / "premiado"
VERSAO = 1  # sobe quando o prompt/as referências mudarem → olha de novo os itens ativos
# Cor do corpo (cor.cor_principal) que vale a pena olhar: marinho e preto (o classificador de
# cor às vezes chama o marinho de "azul escuro" e o preto de "cinza escuro"/"grafite").
_CORPO_ESCURO = ("marinho", "navy", "preto", "negro", "azul escuro", "cinza escuro", "grafite", "chumbo")

_refs_cache: list[str] | None = None


def _refs() -> list[str]:
    global _refs_cache
    if _refs_cache is None:
        _refs_cache = [
            "data:image/jpeg;base64," + base64.b64encode((REFS / f"modelo{n}.jpg").read_bytes()).decode()
            for n in (1, 2, 3)
        ]
    return _refs_cache


def precisa_checar(it: dict) -> bool:
    from ..build.votacao_items import _recente  # mesmo recorte do app/e-mail
    if (it.get("score") or {}).get("decisao") != "compravel":
        return False
    if (it.get("status") or "ativo") != "ativo" or not it.get("fotos"):
        return False
    if (it.get("elastico") or {}).get("tem_elastico") is not True:
        return False  # os 3 modelos têm elástico; o "sósia" sem elástico é outro short
    corpo = ((it.get("cor") or {}).get("cor_principal") or "").lower() if isinstance(it.get("cor"), dict) else ""
    if not any(k in corpo for k in _CORPO_ESCURO):
        return False
    if (it.get("premiado") or {}).get("v") == VERSAO:
        return False
    return _recente(it)


def checar(it: dict) -> dict | None:
    """{"modelo": 1|2|3|None, "confianca", "motivo", ...} ou None se a chamada falhou
    (tenta de novo na próxima rodada)."""
    fotos = (it.get("fotos") or [])[:5]
    conteudo = [
        {"type": "text", "text": prompt.usuario(it.get("titulo") or "")},
        *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in _refs()],
        *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in fotos],
    ]
    try:
        resp = llm.create(
            "sundek:premiado",
            model=IA["model_detalhes"],
            messages=[{"role": "system", "content": prompt.SISTEMA},
                      {"role": "user", "content": conteudo}],
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},
        )
        r = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:  # noqa: BLE001
        print(f"  [premiado] {it.get('id')}: falhou ({str(e)[:100]}) — tenta na próxima rodada")
        return None
    modelo = r.get("modelo")
    modelo = modelo if modelo in (1, 2, 3) else None
    # Confiança baixa ou cós de boardshort: não alarma (alarme falso custa a atenção do cliente).
    if r.get("confianca") == "baixa" or r.get("cos_elastico") is False:
        modelo = None
    return {
        "v": VERSAO,
        "modelo": modelo,
        "nome": prompt.MODELOS.get(modelo) if modelo else None,
        "confianca": r.get("confianca"),
        "cor_corpo": r.get("cor_corpo"),
        "faixas": r.get("faixas"),
        "cos_elastico": r.get("cos_elastico"),
        "modelo_ia": r.get("modelo") if r.get("modelo") in (1, 2, 3) else None,
        "motivo": (r.get("motivo") or "")[:300],
        "em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "_usage": {"prompt_tokens": resp.usage.prompt_tokens,
                   "completion_tokens": resp.usage.completion_tokens, "model": resp.model},
    }
