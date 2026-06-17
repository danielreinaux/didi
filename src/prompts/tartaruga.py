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
    """3 exemplos de calibração:
    - REF 1 POSITIVO fundo (gradiente azul→laranja → multicolor/gradiente)
    - REF 2 CONTRA-EXEMPLO fundo (azul ciano amassado → uniforme, NÃO multicolor)
    - REF 3 CONTRA-EXEMPLO animal (camaleões coloridos → tipo "outro", NÃO tartaruga)
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
                "════════ FIM DAS REFERÊNCIAS — agora vem o ITEM a classificar ════════"
            ),
        },
    ]


SISTEMA = """Você é especialista em classificar shorts Vilebrequin pelo padrão de estampa.

Olhe TODAS as fotos e classifique o padrão principal do short.

O PADRÃO MAIS VALORIZADO É A TARTARUGA GRANDE. Preste atenção na escala.

CATEGORIAS:

TARTARUGA_GRANDE: tartarugas com tamanho GRANDE e visível dominando o tecido.
  O que define "grande": cada tartaruga ocupa uma área equivalente a pelo menos
  1/4 da largura da perna do short. É o padrão característico e mais valorizado.
  ANTES de marcar tartaruga, CONFIRME a anatomia de TARTARUGA (todas abaixo):
    • CASCO oval/redondo (carapaça) ocupando o centro do corpo;
    • cabeça PEQUENA saindo de um lado do casco;
    • 4 patas CURTAS/nadadeiras saindo das laterais do casco;
    • cauda CURTA ou invisível — NUNCA cauda longa/enrolada.
  Inclui: tartarugas de uma cor só, de várias cores ("mistas"), holográficas,
  degrade, prateadas, douradas — desde que tenham o CASCO e o tamanho grande.

TARTARUGA_PEQUENA: tartarugas com tamanho PEQUENO ou MINI formando um padrão repetido
  mais denso no tecido. As tartarugas são reconhecíveis mas pequenas — o tecido
  parece "salpicado" de tartarugas minúsculas. Menos comum e menos valorizado.
  Se ficou em dúvida entre grande e pequena, prefira TARTARUGA_GRANDE.

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
        f'ATENÇÃO ao campo "fundo_padrao": olhe apenas o FUNDO (corpo do tecido), '
        f'ignorando as tartarugas, amassados, sombras e reflexos de luz. Compare '
        f'com REF 1 (gradiente real = multicolor) e REF 2 (azul ciano amassado = '
        f'uniforme, NÃO multicolor). A justificativa deve descrever ESTE item, '
        f'NÃO as referências.'
    )
