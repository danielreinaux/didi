"""Localiza e recorta a CINTURA FRONTAL CENTRAL (fly) do short, ampliada.

Base: src/classify/crop_fly.py do WIP local (não rastreado). Mudanças:
- localizador pede a bbox do SHORT INTEIRO na foto de frente (objeto grande → bbox
  bem mais confiável que pedir a bbox de um snap de 15px) e o recorte do fly é
  DETERMINÍSTICO: faixa central-superior da peça (x 25-75%, y 0-40%), ampliada.
- se houver CLOSE-UP da cintura/braguilha, usa a foto inteira em high.
- localizador em gpt-4o detail=low (85 tok/foto; no mini cada foto low custa ~2.833).
- aceita data URL (harness do gabarito).

Retorna {'crop': <data_url|None>, 'foto_index': int, 'modo': str, 'evidencia': str}.
"""
import base64
import io
import json
import os

import requests
from openai import OpenAI
from PIL import Image

from ..config import IA

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=8)
    return _client


_LOCALIZAR_SISTEMA = """Você analisa fotos de um short de praia. Objetivo: achar a
melhor vista da FRENTE da cintura (onde ficam o cordão e a braguilha).

Olhe as fotos numeradas (0, 1, 2, ...) e responda:
- "close_fly": índice de uma foto que seja um CLOSE-UP da cintura FRONTAL/braguilha
  (a frente do cós ocupa boa parte da foto), ou -1 se não houver.
- "foto_frente": índice da foto que mostra o short INTEIRO visto de FRENTE (cordão/
  braguilha visíveis; NÃO a traseira com bolso/patch), ou -1.
- "bbox_short": bounding box do SHORT INTEIRO nessa foto_frente, normalizada 0-1
  [x0, y0, x1, y1] (x da esquerda p/ direita, y de cima p/ baixo).
- "lado_cintura": em que lado da foto_frente fica a CINTURA (cós) do short —
  "topo" (normal), "direita", "esquerda" ou "baixo" (foto girada/peça deitada de lado).

Responda APENAS JSON:
{"close_fly": <int>, "foto_frente": <int>, "bbox_short": [x0,y0,x1,y1], "lado_cintura": "topo|direita|esquerda|baixo", "evidencia": "<frase curta>"}"""


def _abrir(url: str) -> Image.Image | None:
    try:
        if url.startswith("data:"):
            dados = base64.b64decode(url.split(",", 1)[1])
        else:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            dados = r.content
        return Image.open(io.BytesIO(dados)).convert("RGB")
    except Exception:
        return None


def _data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _localizar(fotos: list[str]) -> dict:
    modelo = os.environ.get("CROP_FLY_MODEL", IA["model_detalhes"])
    conteudo = [{"type": "text", "text": "Fotos numeradas:"}]
    for idx, u in enumerate(fotos):
        conteudo.append({"type": "text", "text": f"Foto {idx}:"})
        conteudo.append({"type": "image_url", "image_url": {"url": u, "detail": "low"}})
    resp = _get_client().chat.completions.create(
        model=modelo,
        messages=[{"role": "system", "content": _LOCALIZAR_SISTEMA},
                  {"role": "user", "content": conteudo}],
        max_tokens=150, temperature=0.1, response_format={"type": "json_object"},
    )
    try:
        from ..utils.cost_tracker import track as _track
        _track("crop_fly_localizar", modelo, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    except Exception:
        pass
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {}


def recortar_fly(item: dict) -> dict:
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"crop": None, "foto_index": -1, "modo": "sem_fotos", "evidencia": "sem fotos"}
    loc = _localizar(fotos)
    n = len(fotos)
    close = loc.get("close_fly", -1)
    frente = loc.get("foto_frente", -1)
    bb = loc.get("bbox_short")
    # 1) faixa central-superior do short inteiro (determinístico a partir da bbox da peça)
    if isinstance(frente, int) and 0 <= frente < n and isinstance(bb, list) and len(bb) == 4:
        img = _abrir(fotos[frente])
        if img is not None:
            w, h = img.size
            x0, y0, x1, y1 = [max(0.0, min(1.0, float(v))) for v in bb]
            gw, gh = x1 - x0, y1 - y0
            if gw > 0.15 and gh > 0.15:
                # faixa generosa junto da CINTURA (a bbox do 4o-low erra uns 5-10%);
                # respeita foto girada (cintura à direita/esquerda/embaixo).
                lado = (loc.get("lado_cintura") or "topo").lower()
                if lado.startswith("dir"):
                    cx0, cx1 = max(0.0, x1 - 0.55 * gw), min(1.0, x1 + 0.08 * gw)
                    cy0, cy1 = y0 + 0.15 * gh, y0 + 0.85 * gh
                elif lado.startswith("esq"):
                    cx0, cx1 = max(0.0, x0 - 0.08 * gw), min(1.0, x0 + 0.55 * gw)
                    cy0, cy1 = y0 + 0.15 * gh, y0 + 0.85 * gh
                elif lado.startswith("bai"):
                    cx0, cx1 = x0 + 0.15 * gw, x0 + 0.85 * gw
                    cy0, cy1 = max(0.0, y1 - 0.55 * gh), min(1.0, y1 + 0.08 * gh)
                else:
                    cx0, cx1 = x0 + 0.15 * gw, x0 + 0.85 * gw
                    cy0, cy1 = max(0.0, y0 - 0.08 * gh), min(1.0, y0 + 0.55 * gh)
                crop = img.crop((int(cx0 * w), int(cy0 * h), int(cx1 * w), int(cy1 * h)))
                cw, ch = crop.size
                esc = max(1.0, 900 / max(cw, ch))
                if esc > 1.0:
                    crop = crop.resize((int(cw * esc), int(ch * esc)), Image.LANCZOS)
                return {"crop": _data_url(crop), "foto_index": frente, "modo": "faixa_central",
                        "foto_frente_url": fotos[frente],
                        "close_fly": close, "evidencia": loc.get("evidencia", "")}
    # 2) close-up da cintura: manda a própria foto (o caller usa detail=high)
    if isinstance(close, int) and 0 <= close < n:
        return {"crop": fotos[close], "foto_index": close, "modo": "close_up", "evidencia": loc.get("evidencia", "")}
    return {"crop": None, "foto_index": -1, "modo": "nao_localizado", "evidencia": loc.get("evidencia", "")}
