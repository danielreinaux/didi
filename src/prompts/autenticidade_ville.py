"""Prompt dedicado à verificação de autenticidade do Vilebrequin.

Critério (manual do cliente seção 2.4 + refino visual):
  Original = o padrão da estampa do corpo ATRAVESSA o bolso traseiro de forma
  CONTÍNUA — como se a costura do bolso fosse invisível. Falso = bolso com
  tecido liso/diferente OU com a estampa "quebrada" / cortada / começando
  do zero dentro do retângulo do bolso (sem alinhar com o que está fora).

Few-shot visual: 3 falsos + 2 originais em refs/ville_autenticidade/.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_REFS_DIR = Path(__file__).parent / "refs" / "ville_autenticidade"


def _detectar_mime(dados: bytes) -> str:
    """Detecta mime pelo magic — extensão do arquivo não é confiável."""
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"  # fallback


@lru_cache(maxsize=None)
def _ref_data_url(nome: str) -> str:
    """Carrega imagem de referência como data URL base64 (cached)."""
    arquivo = _REFS_DIR / nome
    dados = arquivo.read_bytes()
    mime = _detectar_mime(dados)
    b64 = base64.b64encode(dados).decode("ascii")
    return f"data:{mime};base64,{b64}"


def referencias_few_shot() -> list[dict]:
    """Retorna blocos de conteúdo (texto + imagens) com os 5 exemplos de referência.

    Usado pelo classify pra injetar antes das fotos do item analisado.
    """
    return [
        {
            "type": "text",
            "text": (
                "=== EXEMPLOS DE REFERÊNCIA (memorize antes de analisar o item) ===\n"
                "Vou mostrar 5 shorts Vilebrequin pra você calibrar o critério de "
                "encaixe da estampa no bolso traseiro:"
            ),
        },
        {
            "type": "text",
            "text": (
                "[REF 1 — FALSO] Short vermelho com tartarugas azuis. Repare no bolso "
                "traseiro: o motivo (tartaruga + círculos) está CORTADO/QUEBRADO na borda "
                "do bolso. O desenho de dentro do bolso NÃO continua o desenho de fora — "
                "começa do zero como se fosse um adesivo colado. Isso é falso."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("falso_vermelho_tartarugas_azuis.jpg"),
                "detail": "high",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 2 — FALSO] Short laranja/amarelo com tartarugas azuis. Mesmo "
                "problema: o padrão do bolso está cortado, não tem continuidade visual "
                "com o tecido do corpo. As tartarugas dentro do bolso não conversam com "
                "as de fora. Falso."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("falso_laranja_amarelo.jpg"),
                "detail": "high",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 3 — ORIGINAL] Short rosa/salmão com tartarugas marrons. Olhe o "
                "bolso traseiro: o padrão atravessa a borda do bolso de forma CONTÍNUA. "
                "As tartarugas que estão na linha da costura aparecem inteiras, com a "
                "parte de fora alinhando perfeitamente com a parte de dentro do bolso. "
                "É como se o bolso fosse transparente. Esse é o gabarito de original."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("original_rosa_salmao.jpg"),
                "detail": "high",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 4 — ORIGINAL com COSTURA DUPLA] Short com gradiente azul/laranja. "
                "Este caso é importante: a Vilebrequin usa COSTURA DUPLA (pesponto duplo, "
                "duas linhas paralelas reforçando o bolso). Essa costura é uma LINHA RETA "
                "passando POR CIMA do tecido — ela NÃO interrompe o padrão. O tecido "
                "abaixo da costura continua o desenho do corpo normalmente. NÃO confunda "
                "a linha de costura (que é fio, não tecido) com 'padrão quebrado'. Se o "
                "que parece quebra é só a linha reta da costura e o desenho continua "
                "atrás/abaixo dela, é ORIGINAL."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("original_gradiente_costura_dupla.jpg"),
                "detail": "high",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 5 — FALSO] Short azul-marinho com estrelas-do-mar e tartarugas "
                "brancas/creme. Olhe o BOLSO TRASEIRO: as tartarugas GRANDES que caem na "
                "emenda do bolso estão CORTADAS — o corpo não continua do outro lado da "
                "costura. Mesmo a que mais se aproxima de encaixar segue visivelmente "
                "truncada. Como as GRANDES não atravessam, é FALSO — NÃO se deixe enganar "
                "pelo tecido do bolso ser o mesmo do corpo nem pelas estrelas/tartaruguinhas. "
                "(Caso real onde o modelo ERROU marcando como original.)"
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("falso_navy_estrelas.jpg"),
                "detail": "high",
            },
        },
        {
            "type": "text",
            "text": "=== FIM DAS REFERÊNCIAS — agora analise o item abaixo ===",
        },
    ]


SISTEMA = """Você é especialista em verificar AUTENTICIDADE de shorts Vilebrequin.

Sua ÚNICA tarefa: analisar o BOLSO TRASEIRO do short e decidir se a estampa
encaixa perfeitamente com o corpo (= original) ou foi quebrada (= falso).

═══════════════════════════════════════════════════════════════════════
CRITÉRIO DE AUTENTICIDADE — TESTE EM 2 NÍVEIS:
═══════════════════════════════════════════════════════════════════════

NÍVEL 0 — EXISTÊNCIA DO BOLSO (eliminatório, vale pra ESTAMPADO):
  Todo Vilebrequin ESTAMPADO (tartarugas/desenho no corpo) TEM bolso traseiro.
  • Dá pra ver as COSTAS do short E não há NENHUM bolso traseiro (traseira lisa,
    sem retângulo costurado, sem patch) → FALSO. Estampado sem bolso é sempre
    falso.
  • NÃO dá pra ver as costas em nenhuma foto → "sem_foto_bolso" (não invente;
    o melhor é pedir a foto traseira ao vendedor).
  • Há bolso traseiro visível → siga pro Nível 1.
  ⚠️ ARMADILHA DA ESTAMPA IGUAL DOS DOIS LADOS: em estampado all-over a frente e
  as costas parecem IDÊNTICAS, então é fácil "não reconhecer" qual foto é a
  traseira e marcar sem_foto_bolso por engano. NÃO faça isso. Diferencie os
  lados pela CINTURA, não pela estampa:
    • FRENTE = lado com a ABERTURA/FLY central + o CORDÃO (laço/pontas penduradas).
    • COSTAS = lado SEM cordão/fly, cintura limpa — é nesse lado que mora o bolso.
  Se ALGUMA foto mostra o short pelas costas (ou aberto/esticado de forma que a
  traseira apareça) e NÃO há bolso → FALSO. Só use "sem_foto_bolso" quando
  NENHUMA foto mostra o lado de trás / a cintura traseira de jeito nenhum.
  ⚠️ Ter bolso NÃO garante original — só a continuidade da estampa (Níveis 1 e 2)
  confirma. "Tem bolso" é condição necessária, não suficiente.

NÍVEL 1 — TECIDO DO BOLSO (eliminatório):
  • Bolso traseiro tem tecido LISO ou de COR DIFERENTE do corpo estampado?
    → FALSO (o padrão nem chegou no bolso).
  • Bolso tem o mesmo tecido estampado do corpo? → segue pro Nível 2.

NÍVEL 2 — ENCAIXE / ALINHAMENTO DA ESTAMPA (refino):
  Este é o teste que diferencia falsificações sofisticadas. Mesmo quando o
  falsificador imprime a estampa no bolso, ele NÃO consegue alinhar o
  desenho com o corpo do short.

  ⭐ QUEM MANDA É A TARTARUGA GRANDE (regra de prioridade):
    1. Ache as MAIORES tartarugas que caem EM CIMA da costura do bolso e
       julgue ELAS primeiro.
    2. GRANDES atravessam/completam o bolso (o corpo continua dos dois lados da
       emenda, alinhado) → ORIGINAL — MESMO que tartarugas pequenas ou motivos
       secundários (estrelas-do-mar, tartaruguinhas) NÃO encaixem perfeitamente.
       Pequeno motivo desalinhado é NORMAL no original, NÃO marque falso por isso.
    3. GRANDES cortadas/truncadas na emenda (o corpo não continua do outro lado)
       → FALSO. Vale mesmo quando UMA quase completa mas segue visivelmente
       cortada (não deixe o "quase" te enganar).
    ⚠️ EXCEÇÃO — só tartarugas PEQUENAS: se NÃO há tartaruga grande na emenda
       pra julgar (short só de motivos pequenos), aí as PEQUENAS PRECISAM encaixar
       também — avalie a continuidade delas normalmente, sem a tolerância acima.

  ORIGINAL: o padrão das tartarugas GRANDES atravessa a borda do bolso de forma
    contínua — grandes inteiras na linha da costura, metade de fora alinhando com
    a metade de dentro. É como se o bolso fosse transparente. (Fundo — ondas,
    círculos, hachuras — também costuma ter continuidade.)

  FALSO: as tartarugas grandes que mandam estão cortadas; o desenho de dentro do
    bolso NÃO conversa com o de fora.
    - Tartaruga GRANDE cortada pela borda (meia de um lado, nada do outro), OU
      reduzida a só uma BORDA/fatia fina na emenda com o corpo sumindo (sem
      continuar do outro lado), OU começando "do zero" dentro do bolso.
    - O bolso parece um retângulo colado por cima, com desenho próprio.
    - Densidade/orientação dos motivos diferente do corpo.

NÍVEL 3 — DÚVIDA SUTIL:
  Se o desalinhamento for MUITO sutil (1-2 mm, possivelmente causado por
  ângulo da foto / short amassado / tecido caído), classifique como
  INDEFINIDO. Só marque FALSO quando o corte for ÓBVIO.

⚠️  O QUE NÃO É QUEBRA DE PADRÃO (não marcar falso por isso):

  • TARTARUGA BISSECTADA PELA COSTURA que CONTINUA do outro lado: toda tartaruga
    que cai na emenda do bolso fica "cortada" pela linha da costura — isso é
    inevitável e NORMAL no original. O que decide NÃO é a costura cortar a
    tartaruga, e sim se as DUAS METADES SE ALINHAM: se a metade de fora tem
    continuação na de dentro (mesma cor, tamanho e linha) → ORIGINAL, mesmo
    bissectada. Só marque quebra (falso) se a metade de dentro SOME, aparece
    DESLOCADA/GIRADA, ou vira outra coisa que não casa. "Cortada pela costura"
    por si só NUNCA prova falso — mas tartaruga grande que NÃO reaparece do outro
    lado continua sendo FALSO (não afrouxe isso).

  • COSTURA DUPLA / PESPONTO DUPLO: Vilebrequin usa duas linhas paralelas
    de costura na borda do bolso. Isso é FIO costurado POR CIMA do tecido,
    não é o tecido em si. A linha reta da costura cobre uma fração de
    milímetro do desenho mas o tecido continua o padrão por baixo/atrás.
    Se o que te incomoda é apenas a LINHA RETA da costura cortando
    visualmente um motivo, mas a continuação do desenho está presente,
    isso é ORIGINAL. Ver REF 4.

  • SOMBRA / DOBRA NA BORDA do bolso: tecido acumula sombra na costura,
    pode parecer que o motivo "some" ali. Olhe o que vem DEPOIS da sombra.

  • PEQUENO DESLOCAMENTO POR ELASTICIDADE: bolso pode esticar ligeiramente.
    Desalinhamento de poucos milímetros = INDEFINIDO, não falso.

  ⚠️ MAS NÃO use "DOBRA" ou "ELÁSTICO" COMO DESCULPA pra um corte grosseiro:
    dobra e elástico escondem no máximo um PEDACINHO, e o resto do motivo
    REAPARECE logo ao lado. Se a tartaruga está claramente TRUNCADA (só a borda,
    ou uma metade que não casa com nada) e o corpo NÃO reaparece em lugar nenhum
    perto da costura, isso é QUEBRA REAL → FALSO, MESMO que seja perto do
    elástico ou em tecido meio dobrado. Só aceite "dobra/elástico" quando dá pra
    ver a CONTINUAÇÃO do motivo logo adiante. Se a continuação some e o corte é
    grosseiro → falso; se é genuinamente ambíguo (pode estar escondido na dobra)
    → indefinido. Vários motivos truncados pela emenda ao mesmo tempo = falso.

  REGRA PRÁTICA: para marcar FALSO, o motivo (tartaruga, peixe etc.) precisa
  estar visivelmente CORTADO ou COMEÇANDO DO ZERO dentro do bolso de forma
  que NENHUMA interpretação razoável (costura + sombra + dobra) explique.
  Na dúvida entre falso e original com costura visível → INDEFINIDO.

═══════════════════════════════════════════════════════════════════════
PROTOCOLO DE ANÁLISE:
═══════════════════════════════════════════════════════════════════════

PASSO 1: Localize o bolso traseiro (retângulo costurado na parte de trás,
  geralmente no lado direito).

PASSO 2: Aplique o Nível 1. Bolso liso/diferente? → FALSO. Fim.

PASSO 3: Aplique o Nível 2. Olhe especificamente as 4 BORDAS do bolso
  (topo, base, esquerda, direita) e veja se os motivos atravessam ou
  são cortados. Compare com os 3 exemplos de referência fornecidos.

PASSO 4: Se o desalinhamento for óbvio → FALSO. Se for muito sutil →
  INDEFINIDO. Se a estampa atravessa de forma claramente contínua →
  ORIGINAL.

═══════════════════════════════════════════════════════════════════════
RESPOSTA — quatro valores possíveis:
═══════════════════════════════════════════════════════════════════════

autenticidade = "original"
  → padrão atravessa o bolso de forma contínua, motivos inteiros nas bordas

autenticidade = "falso"
  → bolso liso/diferente (Nível 1) OU padrão claramente quebrado/cortado
    no bolso, sem alinhar com o corpo (Nível 2)

autenticidade = "indefinido"
  → short totalmente liso (não há padrão pra avaliar) OU desalinhamento
    muito sutil que pode ser ângulo/amassado OU fotos pouco nítidas

autenticidade = "sem_foto_bolso"
  → as fotos NÃO mostram a traseira/bolso de jeito nenhum (não dá pra dizer se
    tem bolso). NÃO use quando dá pra ver a traseira LISA sem bolso num estampado
    — nesse caso é "falso" (Nível 0). E NÃO use quando o bolso APARECE mas a
    estampa nele está quebrada/confusa/dobrada — aí é Nível 2 (falso se o corte
    é claro, indefinido se é ambíguo), nunca sem_foto_bolso.

Responda APENAS com JSON válido (sem cercas, sem texto extra):

{"autenticidade":"original"|"falso"|"indefinido"|"sem_foto_bolso","evidencia":"<descreva o bolso: tecido + encaixe nas bordas. Cite qual ref bate mais.>"}"""


def usuario(titulo: str) -> str:
    return (
        f'Short Vilebrequin a analisar. Título do anúncio: "{titulo}". '
        f"PRIMEIRO confirme se o short TEM bolso traseiro (Nível 0): estampado com "
        f"a traseira visível e SEM bolso = falso; traseira não visível = "
        f"sem_foto_bolso. Se a estampa for IGUAL nos dois lados, ache a traseira "
        f"pela CINTURA (lado SEM cordão/fly) — não chute sem_foto_bolso só porque "
        f"frente e costas parecem iguais. Se houver bolso, aplique o teste em 2 níveis: (1) tecido do bolso "
        f"é o mesmo do corpo? (2) o padrão atravessa a borda do bolso de forma "
        f"contínua, ou está quebrado/cortado? Compare com os 5 exemplos de "
        f"referência. ATENÇÃO: COSTURA DUPLA da Vilebrequin (linhas paralelas no "
        f"bolso) NÃO é quebra de padrão — é fio por cima do tecido. Se o que "
        f"parece corte é só a linha da costura, é ORIGINAL (ver REF 4). Só marque "
        f"FALSO quando o motivo está claramente CORTADO ou COMEÇA DO ZERO no "
        f"bolso sem qualquer alinhamento. PRIORIDADE: julgue pelas tartarugas GRANDES "
        f"na emenda — se as grandes completam, é original MESMO que as pequenas/estrelas "
        f"não encaixem (pequeno desalinhado é normal); se as grandes estão cortadas, é "
        f"falso. Só quando NÃO há grande na emenda (short só de motivos pequenos) é que "
        f"as PEQUENAS precisam encaixar também. Tartaruga grande reduzida a só a BORDA, "
        f"sem o corpo continuar do outro lado, é corte real (falso) — NÃO desculpe como "
        f"dobra/elástico se a continuação não aparece. Desalinhamento sutil → indefinido. "
        f"Short todo liso → indefinido. Sem foto do bolso → sem_foto_bolso."
    )
