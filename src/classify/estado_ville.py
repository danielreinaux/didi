"""Estado da Ville (desbotado + mancha), só nos candidatos (comprável/médio) — vira AVISO.

Por quê: o gabarito tem só 3 desbotados da Ville, pouco para calibrar um descarte; e o cliente
quer a mancha avisada, não descartada (cv29, /decisoes 04/11/2026: "pode passar, mas botar um
comentário que há mancha"). Então:
  - Haiku 5.5, 3 votos (temperatura 0.7): qualquer voto "sim"/"talvez" → possível desbotado;
    maioria com mancha → aviso de mancha. Bancada: 3/3 desbotados, 8/74 alarmes.
  - Gemini 3.5 Flash-Lite, 1 voto: "sim" junto com o Haiku → desbotado forte (rebaixa para médio).
    Bancada: 1/3 desbotados, 0/74 alarmes.
Custo: ~US$0,003 por candidato (uns 3 por dia). Sem rota/erro → sem aviso (não bloqueia).
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from ..config import IA
from ..prompts import estado_ville as prompt
from ..utils import llm

VOTOS = 3


def _parse(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto or "", re.S)
    try:
        return json.loads(m.group(0) if m else texto)
    except Exception:
        return {"erro": "JSON inválido"}


def _voto(agente: str, conteudo: list, temperatura: float) -> dict:
    try:
        resp = llm.create(
            agente, fallback=False,
            model=IA["model"],
            messages=[{"role": "system", "content": prompt.SISTEMA}, {"role": "user", "content": conteudo}],
            max_tokens=1500,
            temperature=temperatura,
            response_format={"type": "json_object"},
        )
    except Exception as e:  # noqa: BLE001
        return {"erro": str(e)[:120]}
    out = _parse(resp.choices[0].message.content)
    out["_usage"] = {"prompt_tokens": resp.usage.prompt_tokens or 0,
                     "completion_tokens": resp.usage.completion_tokens or 0, "model": resp.model}
    return out


def verificar_estado(item: dict) -> dict:
    """{"desbotado": "forte"|"talvez"|"nao"|None, "mancha": bool, "mancha_onde": str,
    "sinais": str, "votos": {...}, "_usage": [...]}. None = não deu para checar."""
    fotos = (item.get("fotos") or [])[:8]
    if not fotos or not llm.tem_rota("ville:estado"):
        return {"desbotado": None, "mancha": False, "mancha_onde": "", "sinais": "", "votos": {}}
    conteudo = [{"type": "text", "text": prompt.usuario(item.get("titulo") or "")},
                *[{"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in fotos]]
    with ThreadPoolExecutor(VOTOS + 1) as ex:
        fut_h = [ex.submit(_voto, "ville:estado", conteudo, 0.7) for _ in range(VOTOS)]
        fut_g = ex.submit(_voto, "ville:estado_forte", conteudo, 0.1)
        haiku = [f.result() for f in fut_h]
        gemini = fut_g.result()
    validos = [v for v in haiku if v.get("desbotado") in ("sim", "talvez", "nao")]
    usos = [v.pop("_usage") for v in haiku + [gemini] if v.get("_usage")]
    if not validos:
        return {"desbotado": None, "mancha": False, "mancha_onde": "", "sinais": "",
                "votos": {"erro": (haiku[0].get("erro") or "")[:120]}, "_usage": usos}
    haiku_viu = any(v["desbotado"] in ("sim", "talvez") for v in validos)
    gemini_sim = gemini.get("desbotado") == "sim"
    desbotado = "forte" if gemini_sim and haiku_viu else "talvez" if haiku_viu or gemini_sim else "nao"
    com_mancha = [v for v in validos if v.get("mancha") == "sim"]
    mancha = len(com_mancha) * 2 > len(validos)
    ref = next((v for v in validos if v["desbotado"] in ("sim", "talvez")), {})
    return {
        "desbotado": desbotado,
        "mancha": mancha,
        "mancha_onde": ((com_mancha[0].get("mancha_onde") or "") if mancha else "")[:200],
        "sinais": (ref.get("sinais_desbotado") or gemini.get("sinais_desbotado") or "")[:300],
        "votos": {"haiku": [v["desbotado"] for v in validos], "gemini": gemini.get("desbotado"),
                  "mancha": len(com_mancha)},
        "_usage": usos,
    }
