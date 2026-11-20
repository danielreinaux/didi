"""2ª olhada do bolso nos Vilebrequin aprovados como "original" (20/11/2026).

Regra do cliente: no original a estampa continua por cima do bolso de trás; no falso o bolso é
um retalho, e aparecem tartarugas cortadas ou grudadas no contorno. O teste de autenticidade
(autenticidade_ville.py) olha as fotos inteiras e, quando a 1ª leitura diz "original", não
confirma. Assim passaram 2 falsos do Vinted UK (10858019904 e 10863210597): na foto de 800 px o
bolso tem ~250 px, e a IA resume a impressão geral ("mesmo desenho, cores e espaçamento") sem
conferir ponto a ponto.

Aqui, nos aprovados "original" de estampa de tartaruga:
  1. o gpt-6.1-sol (raciocínio baixo) acha a foto do bolso de trás, a caixa do bolso e a
     costura de baixo da aba;
  2. cada borda vira uma faixa ampliada (base da aba, lados, base do bolso), mais o bolso inteiro;
  3. o gpt-6.1-sol (raciocínio médio) recebe antes 2 exemplos marcados (um falso e um original,
     em prompts/refs/bolso/) e a instrução "na dúvida, aponte", e lê 3 vezes.
Se 2 ou mais leituras dizem que o bolso não casa, o score trata o anúncio como "suspeito": desce
para barganha, com o aviso "conferir_bolso". Nunca descarta.

Teste de 20/11/2026 (15 anúncios do gabarito e do UK, fora os 2 usados como exemplo): falsos 4 de
5 avisados, sempre nas 3 leituras (o 5º não tem foto do bolso); originais 9 de 10 sem aviso. O
alarme falso foi um original de tartaruguinhas com pesponto branco grosso (9282792540).
~US$ 0,04 por anúncio. Resultado em item["autenticidade"]["confere"]; roda uma vez por anúncio.
"""
import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

from ..config import VILLE_APP_DESDE
from ..utils import llm

AGENTE_LOCAL = "ville:bolso_local"
AGENTE = "ville:bolso_confere"
LEITURAS = 3
MAX_FOTOS = 8
LADO = 900  # px do lado maior de cada recorte
REFS = Path(__file__).resolve().parent.parent / "prompts" / "refs" / "bolso"

LOCALIZA = """Você vê fotos de um short de banho (numeradas a partir de 0). Ache a foto que mostra MELHOR o bolso TRASEIRO (o bolso de trás, normalmente com aba), o mais de perto e nítido possível.
Responda só JSON: {"foto": <n ou -1>, "bolso": [x0, y0, x1, y1], "aba_base_y": <número>, "topo_do_short": "cima"|"baixo"|"esquerda"|"direita"}
- "bolso": retângulo do bolso inteiro com a aba, em frações de 0 a 1 da largura e da altura DA FOTO como ela está.
- "aba_base_y": altura (fração 0 a 1 da foto) da costura de baixo da aba; null se o bolso não tem aba.
- "topo_do_short": de que lado da foto fica a cintura."""

JUIZ = """Você confere o BOLSO TRASEIRO de um short Vilebrequin, com o critério de um revendedor profissional.
REGRA: no ORIGINAL o bolso é cortado casando com a estampa — a tartaruga que cruza a costura do bolso ou da aba continua inteira do outro lado, e o espaçamento entre as tartarugas é o mesmo do resto do short. No FALSO o bolso é um retalho costurado por cima: aparecem tartarugas CORTADAS na costura (falta um pedaço, e o pedaço não está do outro lado) ou GRUDADAS (encostadas ou sobrepostas a outra, mais perto do que o espaçamento normal, formando um bicho duplo).
Primeiro vêm 2 EXEMPLOS com os pontos marcados: um FALSO (círculos vermelhos: tartarugas sobrepostas na aba e cortada na lateral) e um ORIGINAL (círculos verdes: tartarugas que atravessam a costura e continuam). Depois vêm os RECORTES do short a avaliar: o bolso inteiro e faixas ampliadas de cada borda (base da aba, lado esquerdo, lado direito, base do bolso).
Em cada faixa, olhe UMA POR UMA as tartarugas que encostam na costura: continua do outro lado? está cortada sem continuação? está grudada em outra? Não conte como corte: o PESPONTO (a linha da costura, mesmo grossa ou de cor contrastante) passando por cima de uma tartaruga que continua dos dois lados; dobra, sombra, ruga, aba torta, tartaruga que some na borda da FOTO. Corte é quando o DESENHO da tartaruga acaba na costura e o resto dela não aparece do outro lado.
Esta conferência só gera um AVISO para o comprador olhar as fotos: na dúvida, APONTE o ponto.
Responda só JSON: {"pontos": [{"recorte": "<nome do recorte>", "tipo": "cortada"|"grudada", "onde": "<descrição curta>"}], "bolso_aparece": true|false, "veredito": "nao_casa"|"casa"|"nao_da_pra_ver"}
"nao_casa" se houver 1 ou mais pontos; "casa" se as tartarugas atravessam as costuras e continuam; "nao_da_pra_ver" se os recortes não mostram o bolso."""

_GIRO = {"cima": 0, "baixo": 180, "esquerda": 90, "direita": 270}
_TRANSPOSE = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}


def precisa_conferir(x: dict) -> bool:
    """Ville aprovado, à venda, no app, estampa de tartaruga, autenticidade "original", sem conferência."""
    aut = x.get("autenticidade") if isinstance(x.get("autenticidade"), dict) else {}
    return ((x.get("score") or {}).get("decisao") in ("compravel", "medio")
            and (x.get("status") or "ativo") == "ativo"
            and aut.get("autenticidade") == "original"
            and "confere" not in aut
            and (x.get("classificacao") or {}).get("tipo") in ("tartaruga_grande", "tartaruga_pequena")
            and bool(x.get("fotos"))
            and (x.get("primeiro_visto") or x.get("coletado_em") or "") >= VILLE_APP_DESDE)


def nao_casa(x: dict) -> bool:
    """A 2ª olhada viu o bolso não casar em 2 ou mais leituras (o score trata como suspeito)."""
    aut = x.get("autenticidade") if isinstance(x.get("autenticidade"), dict) else {}
    conf = aut.get("confere") if isinstance(aut.get("confere"), dict) else {}
    return aut.get("autenticidade") == "original" and (conf.get("nao_casa") or 0) >= 2


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


def _data_url(img: Image.Image, qualidade: int = 88) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=qualidade)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _lado(img: Image.Image, n: int) -> Image.Image:
    f = n / max(img.size)
    return img.resize((max(1, int(img.width * f)), max(1, int(img.height * f))), Image.LANCZOS)


def _frac(v, n: int) -> float:
    v = float(v)
    return v / 100 if 1.5 < v <= 100 else (v / n if v > 100 else v)


def recortes(img: Image.Image, loc: dict) -> list[tuple[str, Image.Image]]:
    """[(nome, recorte em pé e ampliado)]: bolso inteiro e uma faixa por borda."""
    w, h = img.size
    b = loc.get("bolso")
    if isinstance(b, list) and len(b) == 1 and isinstance(b[0], list):
        b = b[0]
    x0, y0, x1, y1 = _frac(b[0], w) * w, _frac(b[1], h) * h, _frac(b[2], w) * w, _frac(b[3], h) * h
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    pw, ph = max(20.0, x1 - x0), max(20.0, y1 - y0)

    def corte(a, b_, c, d):
        cl = lambda v, hi: max(0, min(hi, int(v)))
        return img.crop((cl(a, w), cl(b_, h), cl(c, w), cl(d, h)))

    out = [("bolso inteiro", corte(x0 - .25 * pw, y0 - .25 * ph, x1 + .25 * pw, y1 + .25 * ph))]
    ay = loc.get("aba_base_y")
    if ay is not None:
        try:
            ay = _frac(ay, h) * h
            if y0 < ay < y1:
                out.append(("base da aba", corte(x0 - .1 * pw, ay - .18 * ph, x1 + .1 * pw, ay + .18 * ph)))
        except (TypeError, ValueError):
            pass
    out += [("lado esquerdo", corte(x0 - .2 * pw, y0 - .05 * ph, x0 + .2 * pw, y1 + .05 * ph)),
            ("lado direito", corte(x1 - .2 * pw, y0 - .05 * ph, x1 + .2 * pw, y1 + .05 * ph)),
            ("base do bolso", corte(x0 - .1 * pw, y1 - .2 * ph, x1 + .1 * pw, y1 + .2 * ph))]
    giro = _GIRO.get(loc.get("topo_do_short"), 0)
    if giro:
        out = [(n, c.transpose(_TRANSPOSE[giro])) for n, c in out]
    return [(n, _lado(c, LADO)) for n, c in out if c.width > 10 and c.height > 10]


def _chamar(agente: str, sistema: str, conteudo: list, max_tokens: int) -> tuple[dict, dict]:
    resp = llm.create(
        agente, fallback=False, model="",
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": conteudo}],
        max_tokens=max_tokens, temperature=0, response_format={"type": "json_object"},
    )
    try:
        dados = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        dados = {}
    uso = {"model": resp.model, "prompt_tokens": resp.usage.prompt_tokens,
           "completion_tokens": resp.usage.completion_tokens}
    return (dados if isinstance(dados, dict) else {}), uso


def _exemplos() -> list:
    ex = []
    for rotulo, arq in (("EXEMPLO FALSO (pontos em vermelho):", "exemplo_falso.jpg"),
                        ("EXEMPLO ORIGINAL (pontos em verde):", "exemplo_original.jpg")):
        ex += [{"type": "text", "text": rotulo},
               {"type": "image_url", "image_url": {"url": _data_url(Image.open(REFS / arq)), "detail": "high"}}]
    return ex


def conferir(x: dict) -> dict | None:
    """{"nao_casa": n de leituras que viram o bolso não casar, "leituras": [...], "pontos": [...],
    "foto": n (1ª = 1), "bolso_aparece": bool, "_usage": [...]}.
    None = não deu para conferir agora (sem rota ou chamada falhou): tenta na próxima rodada."""
    if not (llm.tem_rota(AGENTE_LOCAL) and llm.tem_rota(AGENTE)):
        return None
    imgs = [im for im in (_abrir(u) for u in (x.get("fotos") or [])[:MAX_FOTOS]) if im is not None]
    if not imgs:  # links mortos: registra para não tentar para sempre
        return {"nao_casa": None, "bolso_aparece": False, "leituras": [], "pontos": [], "_usage": []}
    try:
        conteudo = [{"type": "text", "text": f"{len(imgs)} fotos."}]
        conteudo += [{"type": "image_url", "image_url": {"url": _data_url(_lado(im, 768), 80), "detail": "low"}}
                     for im in imgs]
        loc, u_loc = _chamar(AGENTE_LOCAL, LOCALIZA, conteudo, 1500)
        n = loc.get("foto") if isinstance(loc.get("foto"), int) else -1
        if not (0 <= n < len(imgs)):
            return {"nao_casa": 0, "bolso_aparece": False, "leituras": [], "pontos": [], "_usage": [u_loc]}
        rec = recortes(imgs[n], loc)
        msg = _exemplos() + [{"type": "text", "text": "AGORA O SHORT A AVALIAR:"}]
        for nome, c in rec:
            msg += [{"type": "text", "text": f"Recorte: {nome}"},
                    {"type": "image_url", "image_url": {"url": _data_url(c), "detail": "high"}}]
        with ThreadPoolExecutor(max_workers=LEITURAS) as pool:
            leituras = list(pool.map(lambda _: _chamar(AGENTE, JUIZ, msg, 3000), range(LEITURAS)))
    except Exception as e:  # noqa: BLE001 — 402/429/rede: tenta na próxima rodada
        print(f"  [bolso 2ª olhada] {x.get('id')}: falhou ({str(e)[:100]})")
        return None
    vereditos = [l.get("veredito") for l, _ in leituras]
    pontos = []
    for l, _ in leituras:
        if l.get("veredito") == "nao_casa":
            for p in l.get("pontos") or []:
                if isinstance(p, dict) and len(pontos) < 4:
                    pontos.append(f"{p.get('recorte', '')}: {p.get('onde', '')}"[:160])
    return {"nao_casa": sum(1 for v in vereditos if v == "nao_casa"), "leituras": vereditos,
            "pontos": pontos, "foto": n + 1, "bolso_aparece": any(l.get("bolso_aparece") for l, _ in leituras),
            "_usage": [u_loc] + [u for _, u in leituras]}
