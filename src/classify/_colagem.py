"""Colagem das fotos numa imagem só, para os agentes no gpt-4o-mini (out/2026).

No gpt-4o-mini cada imagem em detail=low custa ~2.833 tokens, seja qual for o tamanho.
Juntar as N fotos numa grade de 512 px (detail=low) custa 2.833 tokens no total: cada
foto fica com ~metade da resolução por lado. Medido no gabarito para a MARCA: é_Sundek/
é_short idênticos à base nos 2 datasets (2 rodadas) e 79/80 de concordância de portão em
80 itens reais de produção. Para TIPO/COR a colagem perdeu acerto (lá vale cortar fotos).
Tudo-ou-nada: se alguma foto não baixar, devolve None e o agente usa as fotos normais.
"""
import base64
import io
import math

import requests
from PIL import Image, ImageDraw


def colagem(fotos: list[str], lado: int = 512) -> str | None:
    imgs = []
    for u in fotos:
        try:
            if u.startswith("data:"):
                dados = base64.b64decode(u.split(",", 1)[1])
            else:
                r = requests.get(u, timeout=15)
                r.raise_for_status()
                dados = r.content
            imgs.append(Image.open(io.BytesIO(dados)).convert("RGB"))
        except Exception:
            return None
    if len(imgs) < 2:
        return None
    n = len(imgs)
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    cw, ch = lado // cols, lado // rows
    canvas = Image.new("RGB", (cw * cols, ch * rows), "white")
    d = ImageDraw.Draw(canvas)
    for i, im in enumerate(imgs):
        im.thumbnail((cw - 4, ch - 4))
        x, y = (i % cols) * cw, (i // cols) * ch
        canvas.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        d.rectangle([x, y, x + cw - 1, y + ch - 1], outline="gray")
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
