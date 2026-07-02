"""Prompt de CLASSIFICAÇÃO — padrão de estampa do Vilebrequin (tartaruga grande/pequena/liso/outro)."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_REFS_DIR = Path(__file__).parent / "refs" / "ville_cor"


def _detectar_mime(dados: bytes) -> str:
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


@lru_cache(maxsize=None)
def _ref_data_url(nome: str) -> str:
    arquivo = _REFS_DIR / nome
    dados = arquivo.read_bytes()
    mime = _detectar_mime(dados)
    b64 = base64.b64encode(dados).decode("ascii")
    return f"data:{mime};base64,{b64}"


def referencias_few_shot() -> list[dict]:
    """5 exemplos de calibração:
    - REF 1 POSITIVO fundo (gradiente azul→laranja → multicolor/gradiente)
    - REF 2 CONTRA-EXEMPLO fundo (azul ciano amassado → uniforme, NÃO multicolor)
    - REF 3 CONTRA-EXEMPLO animal (camaleões coloridos → tipo "outro", NÃO tartaruga)
    - REF 4 EXCEÇÃO dominância (tartaruga entre flores → tartaruga_grande, compra)
    - REF 5 EXCEÇÃO dominância (tartaruga + estrela-do-mar → tartaruga_grande, compra)
    TODO(Marcos 17/06): falta a foto LIMPA de "flores dominam = outro" (negativo)
    — o Marcos vai mandar mais exemplos; adicionar como REF 6 quando chegar.
    """
    return [
        {
            "type": "text",
            "text": (
                "════════ EXEMPLOS DE CALIBRAÇÃO (NÃO são o item a classificar) ════════\n"
                "Você verá 3 fotos de REFERÊNCIA: as 2 primeiras calibram o campo "
                "fundo_padrao, a 3ª calibra a detecção de ANIMAL (tartaruga × parecidos). "
                "ATENÇÃO: estas fotos NÃO são o item que você vai classificar. NUNCA "
                "descreva estas imagens no campo justificativa — a justificativa deve "
                "descrever APENAS o ITEM real que vem DEPOIS das referências."
            ),
        },
        {
            "type": "text",
            "text": (
                "[REF 1 — POSITIVO: fundo_padrao = \"gradiente\"] Esta foto mostra um "
                "short com gradiente real (azul → branco → laranja) atravessando o corpo "
                "do tecido. Múltiplas cores fortes em zonas diferentes do mesmo short. "
                "Esse tipo de fundo é o que deve ser marcado como multicolor/gradiente."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("fundo_multicolor_gradiente.jpg"),
                "detail": "low",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 2 — CONTRA-EXEMPLO: fundo_padrao = \"uniforme\"] Esta foto mostra "
                "um short AZUL CIANO UNIFORME, amassado e com dobras na foto. Variações "
                "de tom causadas por AMASSADOS, DOBRAS, SOMBRAS de iluminação ou "
                "REFLEXOS do tecido NÃO são multicolor. O short é de uma cor só. Mesmo "
                "que partes pareçam mais escuras (por sombra) ou mais claras (por "
                "reflexo de luz), continua sendo \"uniforme\". Só marque "
                "multicolor/gradiente quando houver REGIÕES DE CORES DIFERENTES de "
                "verdade no tecido — não sombra/dobra."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("uniforme_com_amassados.jpg"),
                "detail": "low",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 3 — CONTRA-EXEMPLO de ANIMAL: tipo = \"outro\", NÃO tartaruga] "
                "Esta foto mostra um short com CAMALEÕES coloridos (laranja/vermelho/azul) "
                "sobre fundo navy. NÃO são tartarugas, apesar de coloridos e parecidos à "
                "primeira vista. Repare nos sinais de que NÃO é tartaruga: cada animal tem "
                "uma CAUDA ENROLADA EM ESPIRAL, uma CRISTA/chifres na cabeça e no dorso, e "
                "um CORPO ALONGADO de lagarto (não um casco redondo). Tartaruga de verdade "
                "tem CASCO OVAL/REDONDO liso, cabeça pequena, 4 patas curtas e cauda CURTA "
                "ou invisível — nunca cauda em espiral nem crista. Um short assim deve ser "
                "tipo=\"outro\" com padrao_identificado=\"camaleões\"."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("outro_camaleao_nao_tartaruga.webp"),
                "detail": "low",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 4 — EXCEÇÃO: tipo = \"tartaruga_grande\", NÃO \"outro\"] Short "
                "azul com FLORES (hibiscos) E tartarugas grandes. Apesar das flores, "
                "as tartarugas ainda aparecem e o modelo é COMPRÁVEL. Quando a "
                "tartaruga divide espaço com flores mas continua identificável/se "
                "destaca, NÃO marque \"outro\" só por ter flor — é tartaruga_grande. "
                "(Só vira \"outro\" quando as FLORES dominam e a tartaruga some.)"
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("excecao_tartaruga_nas_flores.jpg"),
                "detail": "low",
            },
        },
        {
            "type": "text",
            "text": (
                "[REF 5 — EXCEÇÃO: tipo = \"tartaruga_grande\"] Short verde-água com "
                "ESTRELAS DO MAR e tartarugas. As tartarugas se DESTACAM por contraste "
                "de cor, então é COMPRÁVEL mesmo havendo estrelas-do-mar. A presença "
                "de estrela-do-mar sozinha NÃO rebaixa pra \"outro\" se a tartaruga "
                "domina pelo contraste."
            ),
        },
        {
            "type": "image_url",
            "image_url": {
                "url": _ref_data_url("excecao_estrela_do_mar.jpg"),
                "detail": "low",
            },
        },
        {
            "type": "text",
            "text": (
                "════════ FIM DAS REFERÊNCIAS — agora vem o ITEM a classificar ════════"
            ),
        },
    ]


SISTEMA = """Você é especialista em classificar shorts Vilebrequin pelo padrão de estampa.

Olhe TODAS as fotos e classifique o padrão principal do short.

O PADRÃO MAIS VALORIZADO É A TARTARUGA GRANDE. Preste atenção na escala.

CATEGORIAS:

TARTARUGA_GRANDE: o padrão CLÁSSICO da Vilebrequin ("Ronde des Tortues"), o mais
  valorizado — e de LONGE o mais comum nos shorts de tartaruga.
  O QUE DECIDE é a LEGIBILIDADE, não o tamanho absoluto: é tartaruga_grande
  sempre que você CONSEGUE VER cada tartaruga como um motivo INDIVIDUAL e
  reconhecível — dá pra distinguir casco, cabeça e patas de cada uma a olho nu.
  Pode haver MUITAS tartarugas repetidas pelo tecido; o que importa é que cada
  uma é um DESENHO DISTINTO e visível, não uma manchinha. Cobre tamanhos MÉDIO
  a GRANDE.
  ⚠️ NÃO exija que a tartaruga seja gigante nem que ocupe uma fração grande da
  perna. Tartaruga de tamanho MÉDIO, claramente identificável e repetida, é
  tartaruga_grande. (Erro comum: encolher tartarugas médias/nítidas pra "pequena".)
  ANTES de marcar tartaruga (de qualquer tamanho), CONFIRME a anatomia:
    • CASCO oval/redondo (carapaça) ocupando o centro do corpo;
    • cabeça PEQUENA saindo de um lado do casco;
    • 4 patas CURTAS/nadadeiras saindo das laterais do casco;
    • cauda CURTA ou invisível — NUNCA cauda longa/enrolada.
  Inclui: tartarugas de uma cor só, de várias cores ("mistas"), holográficas,
  degrade, prateadas, douradas — desde que dê pra RECONHECER cada tartaruga.

TARTARUGA_PEQUENA: SÓ o caso do MICRO-PRINT — tartarugas MINÚSCULAS e MUITO
  densas, tão pequenas que o tecido lê como uma TEXTURA salpicada/pontilhada e
  você MAL distingue uma tartaruga da outra a olho nu (à distância parece um
  padrãozinho de pontinhos, não tartarugas). É um caso RARO e menos valorizado.
  ⚠️ Se você consegue VER e CONTAR tartarugas individuais com clareza, NÃO é
  pequena — é tartaruga_grande. Na MENOR dúvida entre grande e pequena → GRANDE.

LISO: short sem estampa, em cor sólida. Pode ter:
  - bordado discreto (logo Vilebrequin, tartaruga bordada no bolso)
  - detalhe de fita ou cordão colorido na cintura
  O corpo do tecido não tem padrão repetido.

OUTRO: qualquer outro padrão que não seja tartaruga nem liso. Exemplos:
  - OUTROS ANIMAIS parecidos com tartaruga mas que NÃO são: camaleões, lagartos,
    dragões, iguanas, salamandras, dinossauros, sapos, caranguejos, polvos
  - peixes, estrelas do mar, cavalos-marinhos, âncoras, flores, plantas, corais
  - listras, xadrez, geométrico
  - personagens, mapas, fogos de artifício
  Incluir o nome do padrão identificado no campo "padrao_identificado".

⚠️  CUIDADO — ANIMAIS PARECIDOS COM TARTARUGA (erro comum):
  Estampas coloridas de OUTROS animais são facilmente confundidas com tartaruga,
  ainda mais quando o corpo é colorido/texturizado. NÃO marque tartaruga só
  porque há "um animal colorido repetido". Procure a anatomia da tartaruga
  (CASCO oval + cabeça pequena + 4 patas curtas + SEM cauda longa).
  Sinais de que é OUTRO animal (→ tipo "outro", não tartaruga):
    • CAUDA LONGA ou ENROLADA EM ESPIRAL (camaleão, lagarto, cavalo-marinho)
    • CRISTA, chifres, espinhos ou escamas no dorso/cabeça (camaleão, dragão)
    • CORPO ALONGADO de réptil/lagarto, sem casco oval definido
    • patas longas com dedos de agarrar, asas, barbatanas, tentáculos
  Veja a REF 3 (camaleões) como gabarito do que NÃO é tartaruga.
  Na dúvida real entre tartaruga e outro animal, prefira "outro".

⚠️  DOMINÂNCIA — TARTARUGA × FLORES/ESTRELA-DO-MAR (regra do dono 17/06):
  Alguns shorts misturam tartarugas GRANDES com FLORES (hibiscos) ou ESTRELAS
  DO MAR. O que decide o tipo é QUEM DOMINA visualmente a estampa:
    • Se a ÊNFASE é nas FLORES e a tartaruga fica secundária/camuflada (mesma
      cor e escala das flores, "se perde" no meio do desenho) → tipo "outro"
      (NÃO comprável), mesmo que existam tartarugas grandes.
    • Se as TARTARUGAS continuam se DESTACANDO — por contraste de cor, tamanho
      ou nitidez — mesmo havendo flores ou estrelas-do-mar no fundo →
      tartaruga_grande (COMPRÁVEL). Ver REF 4 (tartaruga entre flores) e
      REF 5 (tartaruga + estrela-do-mar): nas duas a tartaruga ainda salta aos
      olhos, então são compráveis.
  Regra prática: "bati o olho e o que salta é tartaruga?" → tartaruga_grande.
  "o que salta são as flores e a tartaruga só aparece quando procuro?" → outro.

INDEFINIDO: fotos insuficientes para classificar (muito borradas, ângulo ruim).

ALÉM DO TIPO, AVALIE:

cor_principal: a cor de fundo do short (não das tartarugas). Use nomes simples:
  "azul", "azul escuro", "navy", "preto", "branco", "verde", "laranja",
  "vermelho", "amarelo", "cinza", "lilás", "roxo", "rosa", "azul bebê", "verde piscina".
  Se o fundo for multicolor/gradiente, escolha a cor que ocupa a maior área —
  MAS marque fundo_padrao corretamente (veja abaixo).

fundo_padrao: avalie a HOMOGENEIDADE do fundo (corpo do short, não das tartarugas).
  Este é um campo CRÍTICO — fundos muito misturados não vendem bem.

  "uniforme": fundo de UMA cor dominante clara. Pode ter variações sutis de
    tom/sombra/iluminação. As tartarugas/motivos podem ser de qualquer cor
    (inclusive multicolor) — isso NÃO afeta o fundo_padrao. Exemplos:
    - fundo navy sólido com tartarugas coloridas = uniforme
    - fundo branco com tartarugas pretas = uniforme
    - fundo laranja com tartarugas azuis = uniforme
    - azul ciano amassado, com partes mais claras (reflexo) e mais escuras
      (sombra/dobra) = uniforme (ver REF 2)
    Mesmo gradientes muito suaves de uma cor só (azul claro → azul médio)
    contam como uniforme.

  "multicolor": fundo com 3+ cores fortes/distintas formando blocos, manchas
    ou regiões grandes. O olho não consegue dizer "qual é a cor do short"
    porque há múltiplas cores competindo no corpo do tecido.

  "gradiente": fundo com transição visível entre 2+ cores fortes diferentes
    (ex: azul → laranja, rosa → azul, verde → amarelo). A transição atravessa
    o short e cria zonas claramente de cores diferentes. Ver REF 1.

  ⚠️  O QUE NÃO É MULTICOLOR/GRADIENTE (REGRA ANTI-FALSO-POSITIVO):
    • AMASSADOS, DOBRAS, VINCOS do tecido → variação de TOM, não de cor.
    • SOMBRAS (de mesa, ângulo da foto, partes que ficam embaixo) → não.
    • REFLEXOS de luz / brilho do tecido em áreas iluminadas → não.
    • Foto com fundo (sofá, grama, mesa) de cor diferente do short → o que
      importa é a cor DO SHORT, não do entorno.
    • Etiqueta interna, costura, elástico de cor diferente → não.
    Em qualquer dúvida entre uniforme e multicolor por causa de iluminação,
    escolha UNIFORME. Só marque multicolor/gradiente quando você vê
    REGIÕES DE COR DIFERENTE pintadas no tecido, não causadas por luz/dobra.

  REGRA PRÁTICA: se você pudesse pintar uma amostra do tecido em uma única
  cor pra mostrar ao cliente, daria? → uniforme. Se precisaria de várias cores
  pra representar fielmente → multicolor/gradiente.

  As TARTARUGAS coloridas/mistas NÃO contam. Só o FUNDO importa aqui.

tartaruga_variedade: descreva brevemente a variação de cores das tartarugas.
  Exemplos: "tartarugas pretas", "tartarugas coloridas mistas", "tartarugas brancas",
  "tartarugas holográficas", "tartarugas azul escuro", "tartarugas vermelhas".
  Null se não for tartaruga.

aparencia: avalie o estado visual do tecido.
  "ok": aspecto novo, cor uniforme.
  "desbotado": cor apagada, aspecto lavado/envelhecido.
  "indefinido": foto não permite avaliar.

⚠️  REGRA ANTI-ALUCINAÇÃO PARA A JUSTIFICATIVA:
  A justificativa deve descrever EXCLUSIVAMENTE o ITEM real que está sendo
  classificado (as fotos do item, que vêm DEPOIS das referências). NUNCA
  descreva o conteúdo das fotos de referência (REF 1, REF 2) no campo
  justificativa. Se o item é um azul ciano liso, escreva "azul ciano liso";
  NÃO escreva "gradiente azul-laranja com tartarugas coloridas" só porque
  você viu isso na referência. Cada campo (tipo, cor_principal, fundo_padrao,
  tartaruga_variedade, justificativa) deve ser sobre o item analisado.

Responda APENAS com JSON válido:

{
  "tipo": "tartaruga_grande" | "tartaruga_pequena" | "liso" | "outro" | "indefinido",
  "cor_principal": "<cor>",
  "fundo_padrao": "uniforme" | "multicolor" | "gradiente" | "indefinido",
  "tartaruga_variedade": "<descrição ou null>",
  "padrao_identificado": "<nome do padrão se tipo=outro, senão null>",
  "aparencia": "ok" | "desbotado" | "indefinido",
  "justificativa": "<frase curta DESCREVENDO O ITEM REAL, não as referências>",
  "confianca": 0.0-1.0
}"""


def usuario(titulo: str) -> str:
    return (
        f'AGORA é o ITEM REAL a classificar (as fotos abaixo). Título: "{titulo}". '
        f'Classifique o padrão de estampa deste item. '
        f'TAMANHO da tartaruga: se dá pra ver e reconhecer cada tartaruga '
        f'individualmente (mesmo médias/repetidas), é tartaruga_grande. Só marque '
        f'tartaruga_pequena no MICRO-PRINT salpicado, onde as tartarugas viram '
        f'pontinhos indistinguíveis. Na dúvida entre grande e pequena → grande. '
        f'ATENÇÃO ao campo "fundo_padrao": olhe apenas o FUNDO (corpo do tecido), '
        f'ignorando as tartarugas, amassados, sombras e reflexos de luz. Compare '
        f'com REF 1 (gradiente real = multicolor) e REF 2 (azul ciano amassado = '
        f'uniforme, NÃO multicolor). A justificativa deve descrever ESTE item, '
        f'NÃO as referências.'
    )
