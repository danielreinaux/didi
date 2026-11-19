"""2ª olhada do elástico nos aprovados do Sundek (19/11/2026).

O agente do elástico (gpt-6.1-sol) às vezes lê as rugas soltas de um cós reto de boardshort como
"franzido regular". O erro é sistemático e repetir a leitura não corrige: no caso que o cliente
apontou (10852341072, "Sundek zwemshort", sem elástico), 4 de 4 leituras disseram elástico.

Nos aprovados com elástico, esta etapa acha a foto do cós visto de trás (gemini-3.5-flash-lite),
recorta e amplia o cós e pergunta de novo a outro modelo (Claude Haiku 5.5), só sobre o cós. Se
ele não vê elástico, o anúncio NÃO é descartado: o score põe o aviso "conferir_elastico" e, quando
a aprovação dependia do elástico, desce de comprável para barganha (classify/score.py).

Piloto (59 shorts com o elástico marcado pelo cliente no gabarito, mais o caso dele): o Haiku
manteve 27 de 29 com elástico, viu "sem elástico" em 27 de 30 sem e acertou o caso do cliente.
Os 2 elásticos que ele não viu (cs17, cs22) são, pela foto de trás, quase iguais a um "sem
elástico" (cs07): por isso aviso, e não corte. O gemini como juiz diz elástico para quase tudo.

Sem as rotas (config.IA_ROTAS) ou com a chamada falhando, nada acontece e a próxima rodada tenta
de novo. Uma vez conferido, o resultado fica em item["elastico"]["confere"] e não roda mais.
"""
import base64
import io
import json

import requests
from PIL import Image

from ..config import APP_DESDE
from ..utils import llm

AGENTE_LOCAL = "sundek:elastico_local"
AGENTE = "sundek:elastico_confere"
MAX_FOTOS = 6
LADO_MINIMO = 1100  # px: o recorte do cós é ampliado até essa largura

LOCALIZA = """Você vê fotos de um short de banho (numeradas a partir de 0, na ordem). Ache a foto que mostra MELHOR o cós (a faixa da cintura) visto DE TRÁS, de preferência estendido; se não houver foto de trás, use a que mostra melhor o cós de frente.
Responda só JSON: {"foto": <n>, "vista": "costas"|"frente", "caixa": [x0, y0, x1, y1], "topo_do_short": "cima"|"baixo"|"esquerda"|"direita"}
- "caixa": retângulo em frações de 0 a 1 da largura e da altura DA FOTO como ela está, cobrindo o cós inteiro (a faixa da cintura de ponta a ponta, com um pouco do tecido logo abaixo).
- "topo_do_short": de que lado da foto fica a borda de cima do short (a cintura)."""

JUIZ = """Você confere o cós de um short de banho. A imagem é um RECORTE AMPLIADO do cós (faixa da cintura), já em pé (cintura em cima).
Decida se o cós tem ELÁSTICO.
- COM elástico: o tecido do cós fica franzido em muitas pregas pequenas, densas e regulares, lado a lado como sanfona, ao longo da faixa (no cós inteiro ou na parte de trás).
- SEM elástico: faixa plana e estruturada, geralmente com pespontos. Pode ter rugas soltas, dobras de uso, ondulações largas ou irregulares do nylon — isso NÃO é elástico.
- Cordão passando por ilhós não diz nada sobre elástico.
Responda só JSON: {"o_que_vejo": "<uma frase>", "pregas_densas_regulares": true|false, "tem_elastico": true|false|null}
Use null só se o recorte não mostra o cós."""

_GIRO = {"cima": 0, "baixo": 180, "esquerda": 90, "direita": 270}  # graus no sentido horário
_TRANSPOSE = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}


def precisa_conferir(it: dict) -> bool:
    """Aprovado, à venda, visto desde que entrou no app, com elástico e ainda não conferido."""
    el = it.get("elastico") if isinstance(it.get("elastico"), dict) else {}
    return ((it.get("score") or {}).get("decisao") in ("compravel", "medio")
            and (it.get("status") or "ativo") == "ativo"
            and el.get("tem_elastico") is True
            and "confere" not in el
            and bool(it.get("fotos"))
            and (it.get("primeiro_visto") or it.get("coletado_em") or "") >= APP_DESDE)


def _abrir(url: str) -> Image.Image | None:
    try:
        if url.startswith("data:"):
            dados = base64.b64decode(url.split(",", 1)[1])
        else:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            dados = r.content
        return Image.open(io.BytesIO(dados)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def _data_url(img: Image.Image, qualidade: int = 90) -> str:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=qualidade)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _reduzida(img: Image.Image, largura: int = 768) -> Image.Image:
    if img.width <= largura:
        return img
    return img.resize((largura, int(img.height * largura / img.width)))


def _caixa(caixa, w: int, h: int) -> tuple[float, float, float, float] | None:
    """[x0, y0, x1, y1] em frações 0–1 (aceita também 0–100 e pixels); None se não serve."""
    try:
        if isinstance(caixa, list) and len(caixa) == 1 and isinstance(caixa[0], list):
            caixa = caixa[0]
        x0, y0, x1, y1 = [float(v) for v in caixa]
    except (TypeError, ValueError):
        return None
    maior = max(x0, y0, x1, y1)
    if maior > 1.5:
        if maior <= 100:
            x0, y0, x1, y1 = x0 / 100, y0 / 100, x1 / 100, y1 / 100
        else:
            x0, y0, x1, y1 = x0 / w, y0 / h, x1 / w, y1 / h
    x0, x1 = sorted((max(0.0, x0), min(1.0, x1)))
    y0, y1 = sorted((max(0.0, y0), min(1.0, y1)))
    if (x1 - x0) < 0.15 or (y1 - y0) < 0.04:
        return None
    return x0, y0, x1, y1


def recortar(img: Image.Image, caixa, topo) -> tuple[Image.Image, str]:
    """Recorte do cós em pé (cintura em cima) e ampliado. Caixa inválida → a foto inteira."""
    w, h = img.size
    cx = _caixa(caixa, w, h)
    if cx:
        x0, y0, x1, y1 = cx
        c = img.crop((int(max(0, x0 - 0.03) * w), int(max(0, y0 - 0.05) * h),
                      int(min(1, x1 + 0.03) * w), int(min(1, y1 + 0.05) * h)))
        modo = "caixa"
    else:
        c, modo = img, "foto_inteira"
    giro = _GIRO.get(topo, 0)
    if giro:
        c = c.transpose(_TRANSPOSE[giro])
    if c.width < LADO_MINIMO:
        c = c.resize((LADO_MINIMO, max(1, int(c.height * LADO_MINIMO / c.width))), Image.LANCZOS)
    return c, modo


def _chamar(agente: str, sistema: str, conteudo: list, max_tokens: int) -> tuple[dict, dict]:
    resp = llm.create(
        agente,
        fallback=False,  # sem rota não confere (nunca cai num modelo caro)
        model="",
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": conteudo}],
        max_tokens=max_tokens, temperature=0, response_format={"type": "json_object"},
    )
    texto = (resp.choices[0].message.content or "{}").strip()
    if "{" in texto:
        texto = texto[texto.find("{"): texto.rfind("}") + 1]
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        dados = {}
    uso = {"model": resp.model, "prompt_tokens": resp.usage.prompt_tokens,
           "completion_tokens": resp.usage.completion_tokens}
    return (dados if isinstance(dados, dict) else {}), uso


def conferir(it: dict) -> dict | None:
    """{"tem_elastico": True|False|None, "o_que_vejo", "foto" (1ª = 1), "vista", "modo", "_usage": [...]}.
    None = não deu para conferir agora (sem rota ou chamada falhou): tenta na próxima rodada."""
    if not (llm.tem_rota(AGENTE_LOCAL) and llm.tem_rota(AGENTE)):
        return None
    imgs = []
    for u in (it.get("fotos") or [])[:MAX_FOTOS]:
        im = _abrir(u)
        if im is not None:
            imgs.append(im)
    if not imgs:  # links mortos: registra para não tentar para sempre
        return {"tem_elastico": None, "o_que_vejo": "fotos indisponíveis", "_usage": []}
    try:
        conteudo = [{"type": "text", "text": f"{len(imgs)} fotos, numeradas de 0 a {len(imgs) - 1}."}]
        conteudo += [{"type": "image_url", "image_url": {"url": _data_url(_reduzida(im), 80), "detail": "low"}}
                     for im in imgs]
        loc, u1 = _chamar(AGENTE_LOCAL, LOCALIZA, conteudo, 3000)
        n = loc.get("foto")
        n = n if isinstance(n, int) and 0 <= n < len(imgs) else 0
        recorte, modo = recortar(imgs[n], loc.get("caixa"), loc.get("topo_do_short"))
        res, u2 = _chamar(AGENTE, JUIZ, [
            {"type": "text", "text": "Recorte do cós:"},
            {"type": "image_url", "image_url": {"url": _data_url(recorte), "detail": "high"}},
        ], 600)
    except Exception as e:  # noqa: BLE001 — 402/429/rede: tenta na próxima rodada
        print(f"  [elástico 2ª olhada] {it.get('id')}: falhou ({str(e)[:100]})")
        return None
    tem = res.get("tem_elastico")
    return {"tem_elastico": tem if isinstance(tem, bool) else None,
            "o_que_vejo": str(res.get("o_que_vejo") or "")[:300],
            "foto": n + 1, "vista": loc.get("vista"), "modo": modo,
            "modelo": u2.get("model"), "_usage": [u1, u2]}
