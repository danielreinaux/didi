"""Localiza e recorta o bolso traseiro nas fotos do anúncio.

Passo 1: vision (gpt-4o-mini) identifica qual foto mostra o bolso traseiro
         e dá a bounding box da região do bolso.
Passo 2: baixa a foto, recorta a região com folga e amplia.

Retorna um data URL (base64) da imagem recortada e ampliada, pronto pra
mandar pro classificador de bolso. Se não achar bolso, retorna None.
"""
import base64
import io
import json
import os

import requests
from openai import OpenAI
from PIL import Image

from ..config import IA
from ..utils.ratelimit import pace_mini

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=8)
    return _client


_LOCALIZAR_SISTEMA = """Você analisa fotos de shorts Sundek para LOCALIZAR o bolso traseiro.

O bolso traseiro fica na parte de TRÁS do short, tipicamente no lado direito,
com um patch pequeno (logo do sol Sundek) costurado sobre ele.

Olhe as fotos numeradas (0, 1, 2, ...) e identifique:
  - Qual foto mostra MELHOR o bolso traseiro / o patch (vista de costas, ou
    close-up do bolso). Se várias mostram, escolha a mais nítida e próxima.
  - A bounding box da REGIÃO DO BOLSO nessa foto, em coordenadas normalizadas
    0.0-1.0: [x0, y0, x1, y1] onde x0,y0 = canto superior esquerdo e
    x1,y1 = canto inferior direito. Enquadre o bolso e o patch com alguma folga.

Se NENHUMA foto mostra o bolso traseiro / a parte de trás do short, retorne
foto_index = -1.

Responda APENAS JSON válido:
{"foto_index": <int>, "bbox": [x0,y0,x1,y1], "evidencia": "<frase curta>"}"""


def _localizar(fotos: list[str]) -> dict:
    conteudo = [{"type": "text", "text": "Localize o bolso traseiro. Fotos numeradas a seguir:"}]
    for idx, u in enumerate(fotos):
        conteudo.append({"type": "text", "text": f"Foto {idx}:"})
        conteudo.append({"type": "image_url", "image_url": {"url": u, "detail": "low"}})

    pace_mini()
    resp = _get_client().chat.completions.create(
        model=IA["model"],
        messages=[
            {"role": "system", "content": _LOCALIZAR_SISTEMA},
            {"role": "user", "content": conteudo},
        ],
        max_tokens=120,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    try:
        from ..utils.cost_tracker import track as _track
        _track("crop_localizar", IA["model"],
               resp.usage.prompt_tokens, resp.usage.completion_tokens)
    except Exception:
        pass
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"foto_index": -1}


def _recortar_imagem(url: str, bbox: list[float]) -> str | None:
    """Baixa a foto, recorta a bbox com folga, amplia. Retorna data URL base64."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

    w, h = img.size
    x0, y0, x1, y1 = bbox
    # folga de 25% em volta da região
    bw, bh = (x1 - x0), (y1 - y0)
    x0 = max(0.0, x0 - bw * 0.25)
    y0 = max(0.0, y0 - bh * 0.25)
    x1 = min(1.0, x1 + bw * 0.25)
    y1 = min(1.0, y1 + bh * 0.25)

    px0, py0, px1, py1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
    if px1 - px0 < 20 or py1 - py0 < 20:
        return None  # região degenerada

    crop = img.crop((px0, py0, px1, py1))

    # amplia para o lado maior ter ~800px (texto do patch fica legível)
    cw, ch = crop.size
    escala = max(1.0, 800 / max(cw, ch))
    if escala > 1.0:
        crop = crop.resize((int(cw * escala), int(ch * escala)), Image.LANCZOS)

    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def recortar_bolso(item: dict) -> dict:
    """Retorna {'crop': <data_url|None>, 'foto_index': int, 'evidencia': str}."""
    fotos = (item.get("fotos") or [])[:6]
    if not fotos:
        return {"crop": None, "foto_index": -1, "evidencia": "sem fotos"}

    loc = _localizar(fotos)
    idx = loc.get("foto_index", -1)
    bbox = loc.get("bbox")

    if idx is None or idx < 0 or idx >= len(fotos) or not bbox or len(bbox) != 4:
        return {"crop": None, "foto_index": -1, "evidencia": loc.get("evidencia", "bolso não localizado")}

    crop = _recortar_imagem(fotos[idx], bbox)
    return {"crop": crop, "foto_index": idx, "evidencia": loc.get("evidencia", "")}
