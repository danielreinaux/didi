"""Prepara as fotos para os agentes de visão: põe em pé as giradas e garante uma foto das costas.

1) Foto girada (pedido do cliente, 13/11/2026). Vendedor fotografa o short de cabeça para baixo
ou deitado de lado, e os agentes oscilam mais nessas fotos. Caso que motivou: 10783999702,
Sundek branco com a listra nas COSTAS e as duas primeiras fotos de cabeça para baixo → o agente
do tipo respondeu listra_na_frente, o anúncio foi descartado e saiu do ar sem o cliente ser
avisado (reprocessado, dá comprável nota 96).
Medição (mesmos anúncios, foto como veio × foto em pé):
  - listra (10784900943, costas numa foto deitada): achou a listra em 2 de 6 × 6 de 6;
  - tipo (10783999702): listra_na_frente em 1 de 8 × 0 de 8.

2) Costas no fim do anúncio (14/11/2026). O scrape passou a guardar até 12 fotos
(scrape/fotos_pagina.py), mas os agentes olham as 6 primeiras (Sundek) ou 8 (Ville). Caso:
10772630323 (Ville), 11 fotos, as costas só na 9 e na 11 → "sem foto do bolso". Quando
nenhuma das 5 primeiras mostra as costas e existe foto das costas depois, ela entra como 6ª.
Quem lê até 5 fotos (marca, tipo, cor, etiqueta) continua vendo exatamente as mesmas.

Como funciona (chamadas baratas, fotos em low):
  1. Só em anúncio com mais de 5 fotos: uma chamada diz a vista de cada foto (frente, costas,
     interno, detalhe) e qual mostra melhor as costas. Daí sai a ordem para os agentes.
  2. Outra chamada diz de que lado da IMAGEM está o cós nas fotos que os agentes vão olhar. As
     fora de "topo" são baixadas, giradas e viram data URL; as outras seguem como URL.
     São duas chamadas de propósito: pedindo lado e vista juntos, em 12 fotos, o modelo errou
     o lado de foto que estava em pé (10772630323, foto 4).
  3. Só os agentes recebem essa versão. O item salvo mantém as URLs originais, na ordem do
     anúncio (o cache por fotos depende disso), e ganha "orientacao": {"giros": [0, 180, ...],
     "ordem": [0, 1, 2, 3, 4, 8, 5, ...]} — graus no sentido horário para cada foto ficar em pé
     e a ordem em que os agentes viram. O app ainda mostra a foto como veio.

O harness do gabarito (src/tests/gabarito) tem pipeline próprio e ainda NÃO passa por aqui.

Conservador de propósito: na dúvida o modelo responde "topo" ou "nd" e a foto NÃO é girada;
close de etiqueta, de tecido ou de detalhe ("nd") nunca gira. Se a chamada falhar, nada muda.
"""
import base64
import io
import json

import requests
from PIL import Image

from ..utils import llm

AGENTE = "orientacao"
MAX_FOTOS = 8        # padrão: os agentes da Ville olham até 8 fotos (os do Sundek, 6)
MAX_TRIAGEM = 12     # fotos que a chamada confere (é o que o scrape guarda por anúncio)
POS_COSTAS = 5       # a foto das costas puxada do fim entra como 6ª
CHAVE_ORIGINAIS = "_fotos_originais"  # só existe entre para_agentes() e restaurar()

# lado da imagem onde está o cós → graus (sentido horário) para a foto ficar em pé
GIRO = {"topo": 0, "baixo": 180, "esquerda": 90, "direita": 270}
# graus no sentido horário → operação do PIL (que gira no sentido ANTI-horário)
_TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
              270: Image.Transpose.ROTATE_90}
VISTAS = ("frente", "costas", "interno", "detalhe", "outro")

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

SISTEMA_VISTA = """Você recebe as fotos numeradas de um anúncio de short de banho. Diga a VISTA de cada foto e
qual delas mostra melhor as COSTAS do short.

VISTA:
- "frente": o short inteiro, ou quase, visto de frente. Aparecem o cordão, os ilhoses ou a braguilha.
- "costas": o short inteiro, ou quase, visto de trás. Aparece o bolso traseiro (com aba, patch ou
  etiqueta de fora) e NÃO aparecem cordão nem ilhoses.
- "interno": o avesso, o forro ou as etiquetas de dentro.
- "detalhe": close de uma parte só (bolso, patch, cordão, tecido, fita métrica), mesmo que seja
  uma parte das costas.
- "outro": não mostra o short, ou não dá para dizer.

"melhor_costas": o número da foto que melhor mostra o short INTEIRO de costas, com o bolso
traseiro visível. Se nenhuma foto mostra as costas, responda -1.

Responda APENAS JSON, com uma entrada por foto, na ordem:
{"fotos": [{"n": 0, "vista": "frente|costas|interno|detalhe|outro"}, ...], "melhor_costas": <número ou -1>}"""


def _chamar(sistema: str, fotos: list[str], max_tokens: int):
    conteudo = [{"type": "text", "text": f"São {len(fotos)} fotos, numeradas de 0 a {len(fotos) - 1}."}]
    for i, u in enumerate(fotos):
        conteudo.append({"type": "text", "text": f"Foto {i}:"})
        conteudo.append({"type": "image_url", "image_url": {"url": u, "detail": "low"}})
    resp = llm.create(
        AGENTE,
        fallback=False,  # sem rota não há triagem (nunca cai num modelo caro)
        model="",
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


def _por_foto(dados: dict, n_fotos: int):
    """(posição da foto, entrada do modelo) para cada entrada válida da resposta."""
    for pos, f in enumerate(dados.get("fotos") or []):
        if isinstance(f, dict):
            n = f.get("n") if isinstance(f.get("n"), int) else pos
            if 0 <= n < n_fotos:
                yield n, f


def triar(fotos: list[str]) -> dict:
    """{"vistas": [...], "melhor_costas": índice ou None, "_usage": {...}}."""
    dados, uso = _chamar(SISTEMA_VISTA, fotos, 500)
    vistas = ["outro"] * len(fotos)
    for n, f in _por_foto(dados, len(fotos)):
        vista = str(f.get("vista") or "").strip().lower()
        if vista in VISTAS:
            vistas[n] = vista
    m = dados.get("melhor_costas")
    melhor = m if isinstance(m, int) and not isinstance(m, bool) and 0 <= m < len(fotos) else None
    return {"vistas": vistas, "melhor_costas": melhor, "_usage": uso}


def detectar(fotos: list[str]) -> dict:
    """{"lados": [...], "notas": [...], "_usage": {...}} — um lado por foto recebida ("nd" onde
    o modelo não respondeu)."""
    dados, uso = _chamar(SISTEMA, fotos, 400)
    lados = ["nd"] * len(fotos)
    notas = [""] * len(fotos)
    for n, f in _por_foto(dados, len(fotos)):
        notas[n] = str(f.get("cos") or "")[:60]
        lado = str(f.get("lado") or "").strip().lower()
        if lado in GIRO:
            lados[n] = lado
    return {"lados": lados, "notas": notas, "_usage": uso}


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


def ordem_para_agentes(vistas: list[str], melhor_costas: int | None = None) -> list[int]:
    """Índices das fotos na ordem em que os agentes devem ver. Igual à do anúncio, a não ser
    que nenhuma das POS_COSTAS primeiras mostre as costas e exista foto das costas depois:
    aí ela (a melhor, ou a primeira marcada "costas") entra na posição POS_COSTAS e as outras
    descem uma casa."""
    base = list(range(len(vistas)))
    if "costas" in vistas[:POS_COSTAS]:
        return base
    depois = [j for j in range(POS_COSTAS, len(vistas)) if vistas[j] == "costas"]
    if melhor_costas is not None and melhor_costas >= POS_COSTAS and melhor_costas < len(vistas):
        j = melhor_costas
    elif depois:
        j = depois[0]
    else:
        return base
    return base[:POS_COSTAS] + [j] + [i for i in base[POS_COSTAS:] if i != j]


def _reordenar(fotos: list, ordem: list[int] | None) -> list:
    """Aplica `ordem` às primeiras len(ordem) fotos; o resto segue atrás. Ordem inválida
    (lista de fotos encolheu, índice repetido) → devolve como está."""
    if not ordem or len(fotos) < len(ordem) or sorted(ordem) != list(range(len(ordem))):
        return fotos
    return [fotos[i] for i in ordem] + list(fotos[len(ordem):])


def _somar_uso(usos: list[dict]) -> dict:
    return {"model": usos[-1]["model"],
            "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usos),
            "completion_tokens": sum(u.get("completion_tokens", 0) for u in usos)}


def endireitar(item: dict, max_fotos: int = MAX_FOTOS) -> tuple[dict, dict | None]:
    """(item para os agentes, registro). O item devolvido é o MESMO quando nada mudou; senão é
    uma cópia com "fotos" na ordem dos agentes e data URL nas giradas. O registro traz "giros"
    (por foto, na ordem do anúncio), "ordem" (None se igual à do anúncio), "lados", "vistas" e
    "_usage" (soma das chamadas); é None quando o agente não tem rota ou o item não tem foto.
    max_fotos = quantas fotos os agentes daquela marca chegam a olhar; só essas são conferidas."""
    fotos = list(item.get("fotos") or [])
    if not fotos or not llm.tem_rota(AGENTE):
        return item, None
    alvo = fotos[:MAX_TRIAGEM]
    usos, vistas = [], None
    ordem = list(range(len(alvo)))
    if len(alvo) > POS_COSTAS:  # com até 5 fotos todo agente já vê todas: não há o que puxar
        try:
            tri = triar(alvo)
            usos.append(tri["_usage"])
            vistas = tri["vistas"]
            ordem = ordem_para_agentes(vistas, tri["melhor_costas"])
        except Exception as e:  # noqa: BLE001 — sem a vista, segue na ordem do anúncio
            print(f"  [orientacao] vista falhou ({str(e)[:80]}) → ordem do anúncio")
    janela = ordem[:max_fotos]  # as fotos que os agentes desta marca vão olhar, já na ordem
    det = detectar([alvo[i] for i in janela])
    usos.append(det["_usage"])
    giros = [0] * len(alvo)
    lados = ["nd"] * len(alvo)
    novas = list(alvo)
    for pos, lado in enumerate(det["lados"]):
        i = janela[pos]
        lados[i] = lado
        g = GIRO.get(lado, 0)
        girada = girar(alvo[i], g) if g else None
        if girada:  # foto que não baixou segue como está (giro 0)
            novas[i] = girada
            giros[i] = g
    mudou_ordem = ordem != list(range(len(alvo)))
    reg = {"lados": lados, "vistas": vistas, "giros": giros,
           "ordem": ordem if mudou_ordem else None, "_usage": _somar_uso(usos)}
    if not any(giros) and not mudou_ordem:
        return item, reg
    return {**item, "fotos": _reordenar(novas, ordem) + fotos[MAX_TRIAGEM:]}, reg


# ── Encaixe nos pipelines (classify/run.py e classify/ville_run.py) ────────────────────────
# para_agentes() logo depois da checagem de marca; restaurar() no resultado, antes de salvar.

def para_agentes(item: dict, max_fotos: int = MAX_FOTOS) -> tuple[dict, dict]:
    """(item que os agentes devem ver, uso de tokens da chamada — {} se não houve chamada).
    Quando alguma foto girou ou mudou de lugar, o item devolvido é uma cópia com essas fotos,
    o registro em "orientacao" e as URLs originais guardadas para restaurar(). Erro aqui nunca
    derruba o anúncio: os agentes seguem com as fotos como vieram."""
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
    registro = {}
    if any(reg["giros"]):
        registro["giros"] = reg["giros"]
    if reg["ordem"]:
        registro["ordem"] = reg["ordem"]
    return {**item_ia, CHAVE_ORIGINAIS: item.get("fotos"), "orientacao": registro}, reg["_usage"]


def girou(item: dict) -> bool:
    """True se o item devolvido por para_agentes() teve foto girada ou puxada nesta análise."""
    return CHAVE_ORIGINAIS in item


def resumo(item: dict) -> str:
    """Texto curto para o log da rodada: o que foi mexido nas fotos deste item."""
    reg = item.get("orientacao") or {}
    partes = []
    if any(reg.get("giros") or []):
        partes.append(f"giros {reg['giros']}")
    if reg.get("ordem"):
        partes.append(f"costas: foto {reg['ordem'][POS_COSTAS] + 1} entrou como {POS_COSTAS + 1}ª")
    return ", ".join(partes)


def reaplicar(item: dict) -> dict:
    """Cópia do item com as fotos como os agentes viram, pelo registro já salvo ("orientacao"),
    sem chamar o modelo de novo. Para os 2ºs olhares que rodam depois de o item voltar às URLs
    originais (listra de uma cor, desbotado, premiado). Devolve o próprio item se não há o que
    aplicar."""
    reg = item.get("orientacao") or {}
    giros = reg.get("giros") or []
    fotos = list(item.get("fotos") or [])
    mudou = False
    for i, g in enumerate(giros[:len(fotos)]):
        nova = girar(fotos[i], g) if g else None
        if nova:
            fotos[i] = nova
            mudou = True
    reordenadas = _reordenar(fotos, reg.get("ordem"))
    if reordenadas is not fotos:
        fotos, mudou = reordenadas, True
    return {**item, "fotos": fotos} if mudou else item


def restaurar(resultado: dict) -> dict:
    """Repõe as URLs originais das fotos no resultado: data URL e ordem trocada são só para os
    agentes, não vão para o acervo. Sem efeito em anúncio que não teve foto mexida."""
    originais = resultado.pop(CHAVE_ORIGINAIS, None)
    if originais is not None:
        resultado["fotos"] = originais
    return resultado
