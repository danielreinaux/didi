"""Põe em pé as fotos giradas antes de os agentes de visão olharem (pedido do cliente, 13/11/2026).

Vendedor fotografa o short de cabeça para baixo ou deitado de lado, e os agentes oscilam mais
nessas fotos. Caso que motivou: 10783999702, Sundek branco com a listra nas COSTAS e as duas
primeiras fotos de cabeça para baixo → o agente do tipo respondeu listra_na_frente, o anúncio
foi descartado e saiu do ar sem o cliente ser avisado (reprocessado, dá comprável nota 96).

Medição (13/11/2026, mesmos anúncios, foto como veio × foto em pé):
  - listra (10784900943, costas numa foto deitada): achou a listra em 2 de 6 × 6 de 6;
  - tipo (10783999702): listra_na_frente em 1 de 8 × 0 de 8.

Como funciona:
  1. Uma chamada barata (fotos em low) diz, foto a foto, de que lado da IMAGEM está o cós.
  2. As fotos fora de "topo" são baixadas, giradas e viram data URL; as outras seguem como URL.
  3. Só os agentes recebem as fotos giradas. O item salvo mantém as URLs originais e ganha
     "orientacao": {"giros": [0, 180, ...]} — graus no sentido horário que cada foto precisa
     girar para ficar em pé. O app ainda mostra a foto como veio; o número fica salvo para isso.

O harness do gabarito (src/tests/gabarito) tem pipeline próprio e ainda NÃO passa por aqui.

Conservador de propósito: na dúvida o modelo responde "topo" ou "nd" e a foto NÃO é girada;
close de etiqueta, de tecido ou de detalhe ("nd") nunca gira. Se a chamada falhar, nada gira.
"""
import base64
import io
import json

import requests
from PIL import Image

from ..utils import llm

AGENTE = "orientacao"
MAX_FOTOS = 8  # padrão: os agentes da Ville olham até 8 fotos (os do Sundek, 6)
CHAVE_ORIGINAIS = "_fotos_originais"  # só existe entre para_agentes() e restaurar()

# lado da imagem onde está o cós → graus (sentido horário) para a foto ficar em pé
GIRO = {"topo": 0, "baixo": 180, "esquerda": 90, "direita": 270}
# graus no sentido horário → operação do PIL (que gira no sentido ANTI-horário)
_TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
              270: Image.Transpose.ROTATE_90}

SISTEMA = """Você recebe as fotos numeradas de um anúncio de short de banho. Para CADA foto, diga de que
lado da IMAGEM está o CÓS (a cintura) do short.

Como reconhecer as partes:
- CÓS: a borda única que dá a volta na cintura. Costuma ser franzida pelo elástico e ter, na
  frente, os ilhoses e o cordão de amarrar.
- PERNAS: terminam em duas aberturas separadas (as barras), com o gancho no meio (a costura
  entre as pernas). O cós fica sempre do lado OPOSTO às duas barras.

Respostas possíveis:
- "topo": cós em cima e barras das pernas embaixo. É a foto normal, em pé.
- "baixo": cós embaixo e barras das pernas em cima. O short está de cabeça para baixo.
- "direita": cós do lado direito da imagem e barras do lado esquerdo (short deitado).
- "esquerda": cós do lado esquerdo da imagem e barras do lado direito (short deitado).
- "nd": não dá para dizer. Use em close de etiqueta, de tecido, de bolso ou de outro detalhe; em
  peça dobrada ou embolada; em foto que não mostra o short; e sempre que o cós e as barras das
  pernas não aparecem juntos na foto.

Como decidir:
- Primeiro ache o cós (elástico franzido, ilhoses, cordão) e as duas barras das pernas. Depois
  veja em que lado da imagem o cós está. Não presuma que a foto está em pé.
- Ignore o fundo e a direção da luz. Patch ou logo de cabeça para baixo no short inteiro é sinal
  de foto girada. O sentido do texto num close de etiqueta não conta.
- Short inclinado: escolha o lado mais próximo.
- Vale para a frente e para as costas do short.
- Só responda "baixo", "direita" ou "esquerda" quando o cós estiver claramente desse lado.

Responda APENAS JSON, com uma entrada por foto, na ordem. Em "cos" diga em poucas palavras onde
você viu o cós (ex.: "elástico e cordão embaixo"), e só depois o lado:
{"fotos": [{"n": 0, "cos": "<até 6 palavras>", "lado": "topo|baixo|direita|esquerda|nd"}, ...]}"""


def detectar(fotos: list[str]) -> dict:
    """{"lados": [...], "_usage": {...}} — um lado por foto recebida ("nd" onde o modelo não respondeu)."""
    conteudo = [{"type": "text", "text": f"São {len(fotos)} fotos, numeradas de 0 a {len(fotos) - 1}."}]
    for i, u in enumerate(fotos):
        conteudo.append({"type": "text", "text": f"Foto {i}:"})
        conteudo.append({"type": "image_url", "image_url": {"url": u, "detail": "low"}})
    resp = llm.create(
        AGENTE,
        fallback=False,  # sem rota não há endireitamento (nunca cai num modelo caro)
        model="",
        messages=[{"role": "system", "content": SISTEMA}, {"role": "user", "content": conteudo}],
        max_tokens=400, temperature=0, response_format={"type": "json_object"},
    )
    try:
        dados = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        dados = {}
    lados = ["nd"] * len(fotos)
    notas = [""] * len(fotos)
    for pos, f in enumerate(dados.get("fotos") or []):
        if not isinstance(f, dict):
            continue
        n = f.get("n") if isinstance(f.get("n"), int) else pos
        lado = str(f.get("lado") or "").strip().lower()
        if 0 <= n < len(fotos):
            notas[n] = str(f.get("cos") or "")[:60]
            if lado in GIRO:
                lados[n] = lado
    return {"lados": lados, "notas": notas, "_usage": {"model": resp.model,
                                       "prompt_tokens": resp.usage.prompt_tokens,
                                       "completion_tokens": resp.usage.completion_tokens}}


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


def girar(url: str, graus: int) -> str | None:
    """Data URL da foto girada `graus` no sentido horário; None se não deu para baixar."""
    op = _TRANSPOSE.get(graus)
    img = _abrir(url) if op else None
    if img is None:
        return None
    buf = io.BytesIO()
    img.transpose(op).save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def endireitar(item: dict, max_fotos: int = MAX_FOTOS) -> tuple[dict, dict | None]:
    """(item para os agentes, registro). O item devolvido é o MESMO quando nada girou; quando
    girou, é uma cópia com "fotos" trocadas (data URL nas giradas). O registro traz "lados",
    "giros" e "_usage"; é None quando o agente não tem rota ou o item não tem foto.
    max_fotos = quantas fotos os agentes daquela marca chegam a olhar (o resto nem é conferido)."""
    fotos = list(item.get("fotos") or [])
    if not fotos or not llm.tem_rota(AGENTE):
        return item, None
    alvo = fotos[:max_fotos]
    det = detectar(alvo)
    giros = [0] * len(alvo)
    novas = list(fotos)
    for i, lado in enumerate(det["lados"]):
        g = GIRO.get(lado, 0)
        if not g:
            continue
        girada = girar(alvo[i], g)
        if girada:  # foto que não baixou segue como está (giro 0)
            novas[i] = girada
            giros[i] = g
    reg = {"lados": det["lados"], "giros": giros, "_usage": det["_usage"]}
    if not any(giros):
        return item, reg
    return {**item, "fotos": novas}, reg


# ── Encaixe nos pipelines (classify/run.py e classify/ville_run.py) ────────────────────────
# para_agentes() logo depois da checagem de marca; restaurar() no resultado, antes de salvar.

def para_agentes(item: dict, max_fotos: int = MAX_FOTOS) -> tuple[dict, dict]:
    """(item que os agentes devem ver, uso de tokens da chamada — {} se não houve chamada).
    Quando alguma foto girou, o item devolvido é uma cópia com as fotos em pé, o registro em
    "orientacao" e as URLs originais guardadas para restaurar(). Erro aqui nunca derruba o
    anúncio: os agentes seguem com as fotos como vieram."""
    try:
        item_ia, reg = endireitar(item, max_fotos)
    except Exception as e:  # noqa: BLE001
        print(f"  [orientacao] falhou ({str(e)[:100]}) → fotos como vieram")
        return item, {}
    if reg is None:
        return item, {}
    if item_ia is item:
        if "orientacao" in item:  # registro de uma análise anterior, com outras fotos
            item = {k: v for k, v in item.items() if k != "orientacao"}
        return item, reg["_usage"]
    return ({**item_ia, CHAVE_ORIGINAIS: item.get("fotos"), "orientacao": {"giros": reg["giros"]}},
            reg["_usage"])


def girou(item: dict) -> bool:
    """True se o item devolvido por para_agentes() teve foto girada nesta análise."""
    return CHAVE_ORIGINAIS in item


def reaplicar(item: dict) -> dict:
    """Cópia do item com as fotos em pé pelo registro já salvo ("orientacao.giros"), sem chamar
    o modelo de novo. Para os 2ºs olhares que rodam depois de o item voltar às URLs originais
    (listra de uma cor, desbotado, premiado). Devolve o próprio item se nada foi girado."""
    giros = (item.get("orientacao") or {}).get("giros") or []
    fotos = list(item.get("fotos") or [])
    mudou = False
    for i, g in enumerate(giros[:len(fotos)]):
        nova = girar(fotos[i], g) if g else None
        if nova:
            fotos[i] = nova
            mudou = True
    return {**item, "fotos": fotos} if mudou else item


def restaurar(resultado: dict) -> dict:
    """Repõe as URLs originais das fotos no resultado: data URL é só para os agentes, não vai
    para o acervo. Sem efeito em anúncio que não teve foto girada."""
    originais = resultado.pop(CHAVE_ORIGINAIS, None)
    if originais is not None:
        resultado["fotos"] = originais
    return resultado
