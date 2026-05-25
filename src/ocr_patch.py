"""OCR local pra ler a palavra SUNDEK no patch do bolso traseiro.

Estratégia:
  1. Recebe o crop do bolso (data URL base64 vindo do crop_bolso.py).
  2. Roda EasyOCR procurando texto.
  3. Se achar "SUNDEK" (ou variação tolerante a erro de leitura) → tem_nome=True.
  4. Se NÃO achar texto algum, retorna None (significa "não tenho certeza,
     deixa o fallback pro gpt-4o decidir").
  5. Se achar OUTRO texto que claramente não é SUNDEK → tem_nome=False
     (raro — patches Sundek com texto sempre têm SUNDEK).

OCR é grátis (CPU local). Só puxa o gpt-4o caro quando OCR não viu nada.
"""
import base64
import io
import re
import threading

from PIL import Image

_reader = None
_reader_lock = threading.Lock()


def _get_reader():
    """Lazy init — EasyOCR carrega modelos pesados, só faz na 1ª chamada."""
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr  # import lazy: evita carregar quando OCR não é usado
            _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


# Variações comuns de "SUNDEK" que OCR pode confundir
_PAD_RE = re.compile(r'\bs[uoa0]nd[e3][ckg]\b', re.IGNORECASE)


def ler_patch(crop_data_url: str | None) -> dict:
    """Retorna {'tem_nome': True|False|None, 'texto_lido': str, 'metodo': 'ocr'}.

    None = OCR não conseguiu ler nada com certeza → fallback ao gpt-4o.
    True = leu "SUNDEK" (ou variação aceitável).
    False = leu texto distinto que claramente não é SUNDEK.
    """
    if not crop_data_url or not crop_data_url.startswith("data:image"):
        return {"tem_nome": None, "texto_lido": "", "metodo": "ocr_skip_sem_crop"}

    try:
        # parse data URL → bytes
        b64 = crop_data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        return {"tem_nome": None, "texto_lido": f"erro_decode: {e}", "metodo": "ocr_erro"}

    # EasyOCR aceita ndarray
    try:
        import numpy as np
        reader = _get_reader()
        # paragraph=False, detail=1 retorna lista de (bbox, texto, confidence)
        results = reader.readtext(np.array(img), detail=1, paragraph=False)
    except Exception as e:
        return {"tem_nome": None, "texto_lido": f"erro_ocr: {e}", "metodo": "ocr_erro"}

    # filtra resultados com confidence aceitável
    textos = []
    for bbox, txt, conf in results:
        if not txt or not txt.strip():
            continue
        if conf < 0.30:
            continue
        textos.append((txt.strip(), conf))

    if not textos:
        return {"tem_nome": None, "texto_lido": "(vazio)", "metodo": "ocr_nada_visivel"}

    # Procura "SUNDEK" ou variação
    todos_juntos = " ".join(t for t, _ in textos)
    if _PAD_RE.search(todos_juntos):
        return {"tem_nome": True, "texto_lido": todos_juntos, "metodo": "ocr_encontrou_sundek"}

    # Tem texto mas não é SUNDEK
    # Cuidado: pode ser um patch antigo SEM nome, mas o OCR pegou alguma sujeira/sombra.
    # Conservador: só retorna False se o texto for substancial (>=3 chars relevantes).
    chars_letras = sum(1 for c in todos_juntos if c.isalpha())
    if chars_letras >= 3:
        return {"tem_nome": False, "texto_lido": todos_juntos, "metodo": "ocr_texto_outro"}

    # Pouca evidência — deixa o gpt-4o decidir
    return {"tem_nome": None, "texto_lido": todos_juntos, "metodo": "ocr_inconclusivo"}
