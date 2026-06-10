"""Prompt dedicado à verificação de autenticidade do Vilebrequin.

Critério (manual do cliente seção 2.4 + refino visual):
  Original = o padrão da estampa do corpo ATRAVESSA o bolso traseiro de forma
  CONTÍNUA — como se a costura do bolso fosse invisível. Falso = bolso com
  tecido liso/diferente OU com a estampa "quebrada" / cortada / começando
  do zero dentro do retângulo do bolso (sem alinhar com o que está fora).

Few-shot visual: 2 falsos + 1 original em refs/ville_autenticidade/.
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
    """Retorna blocos de conteúdo (texto + imagens) com os 3 exemplos de referência.

    Usado pelo classify pra injetar antes das fotos do item analisado.
    """
    return [
        {
            "type": "text",
            "text": (
                "=== EXEMPLOS DE REFERÊNCIA (memorize antes de analisar o item) ===\n"
                "Vou mostrar 3 shorts Vilebrequin pra você calibrar o critério de "
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
            "text": "=== FIM DAS REFERÊNCIAS — agora analise o item abaixo ===",
        },
    ]


SISTEMA = """Você é especialista em verificar AUTENTICIDADE de shorts Vilebrequin.

Sua ÚNICA tarefa: analisar o BOLSO TRASEIRO do short e decidir se a estampa
encaixa perfeitamente com o corpo (= original) ou foi quebrada (= falso).

═══════════════════════════════════════════════════════════════════════
CRITÉRIO DE AUTENTICIDADE — TESTE EM 2 NÍVEIS:
═══════════════════════════════════════════════════════════════════════

NÍVEL 1 — TECIDO DO BOLSO (eliminatório):
  • Bolso traseiro tem tecido LISO ou de COR DIFERENTE do corpo estampado?
    → FALSO (o padrão nem chegou no bolso).
  • Bolso tem o mesmo tecido estampado do corpo? → segue pro Nível 2.

NÍVEL 2 — ENCAIXE / ALINHAMENTO DA ESTAMPA (refino):
  Este é o teste que diferencia falsificações sofisticadas. Mesmo quando o
  falsificador imprime a estampa no bolso, ele NÃO consegue alinhar o
  desenho com o corpo do short.

  ORIGINAL: o padrão do corpo ATRAVESSA a borda do bolso de forma contínua.
    - Motivos (tartaruga, peixe, flor etc.) que ficam na linha da costura
      do bolso aparecem INTEIROS, com a metade de fora alinhando com a
      metade de dentro do bolso.
    - É como se o bolso fosse transparente — você não nota a costura
      atrapalhando o desenho.
    - O fundo (ondas, círculos, hachuras) também tem continuidade.

  FALSO: o padrão dentro do bolso NÃO conversa com o de fora.
    - Motivos cortados pela borda do bolso (meia tartaruga de um lado,
      nada do outro), OU motivos começando "do zero" dentro do bolso.
    - O bolso parece um retângulo colado por cima, com desenho próprio.
    - Densidade/orientação dos motivos diferente do corpo.

NÍVEL 3 — DÚVIDA SUTIL:
  Se o desalinhamento for MUITO sutil (1-2 mm, possivelmente causado por
  ângulo da foto / short amassado / tecido caído), classifique como
  INDEFINIDO. Só marque FALSO quando o corte for ÓBVIO.

⚠️  O QUE NÃO É QUEBRA DE PADRÃO (não marcar falso por isso):

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
  → as fotos NÃO mostram o bolso traseiro de jeito nenhum

Responda APENAS com JSON válido (sem cercas, sem texto extra):

{"autenticidade":"original"|"falso"|"indefinido"|"sem_foto_bolso","evidencia":"<descreva o bolso: tecido + encaixe nas bordas. Cite qual ref bate mais.>"}"""


def usuario(titulo: str) -> str:
    return (
        f'Short Vilebrequin a analisar. Título do anúncio: "{titulo}". '
        f"Olhe o BOLSO TRASEIRO. Aplique o teste em 2 níveis: (1) tecido do bolso "
        f"é o mesmo do corpo? (2) o padrão atravessa a borda do bolso de forma "
        f"contínua, ou está quebrado/cortado? Compare com os 4 exemplos de "
        f"referência. ATENÇÃO: COSTURA DUPLA da Vilebrequin (linhas paralelas no "
        f"bolso) NÃO é quebra de padrão — é fio por cima do tecido. Se o que "
        f"parece corte é só a linha da costura, é ORIGINAL (ver REF 4). Só marque "
        f"FALSO quando o motivo está claramente CORTADO ou COMEÇA DO ZERO no "
        f"bolso sem qualquer alinhamento. Desalinhamento sutil → indefinido. "
        f"Short todo liso → indefinido. Sem foto do bolso → sem_foto_bolso."
    )
