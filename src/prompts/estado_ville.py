"""Prompt do ESTADO da Ville (desbotado + mancha) — vira AVISO no app, não descarte.

Bancada 05/11/2026 (77 itens do gabarito da Ville, só 3 desbotados): Haiku 5.5 com 3 votos pega
os 3 como "sim/talvez" com 8 alarmes em 74; Gemini 3.5 Flash-Lite diz "sim" só no óbvio
(9254763758) e nenhum alarme falso; a mancha do cv29 (cliente: "pode passar, mas avisar")
aparece nos 3 votos do Haiku. Ver classify/estado_ville.py.
"""
SISTEMA = """Você avalia o ESTADO DE CONSERVAÇÃO de um short de banho Vilebrequin usado, para um revendedor
exigente. Olhe TODAS as fotos com atenção (abra o zoom mental em cada uma) e responda duas coisas.

# 1. DESBOTADO / GASTO
Sinais (basta UM evidente para "sim"; sinal fraco ou só numa foto → "talvez"):
- COR LAVADA: o tecido perdeu cor de forma geral ou IRREGULAR — partes mais claras/esbranquiçadas que
  o resto (frente × costas, barra, cós, bordas dos bolsos), aspecto "stonewash"/calcário, preto que
  virou cinza, marinho que virou azul-acinzentado, vermelho/laranja que virou salmão manchado.
  Compare com as partes protegidas: dentro do cós, atrás da aba do bolso, perto das costuras.
- TARTARUGAS GASTAS: na Vilebrequin as tartarugas muitas vezes são FLOCADAS (aveludadas, em relevo,
  cor sólida e opaca). Gastas, ficam falhadas, manchadas ou com a cor apagada (marrom/acinzentada em
  vez de preta/marinho), com o tecido do fundo aparecendo por dentro. Tartarugas estampadas comuns
  gastas ficam pálidas, sem contraste com o fundo.
- CONJUNTO APAGADO: todas as cores do short parecem esmaecidas, como uma foto com o contraste baixo,
  enquanto a etiqueta ou o cordão na mesma foto mostram cores vivas.
NÃO é desbotado: cor uniforme de fábrica (inclusive pastel e neon); degradê ou tie-dye de fábrica;
diferença de luz, sombra, flash ou balanço de branco entre fotos; tecido amassado; fiapos.

# 2. MANCHA
"sim" se há mancha, respingo, marca de água sanitária, encardido ou amarelado visível em alguma foto
(mesmo pequena). Diga ONDE (foto e parte do short). Sombra, dobra, reflexo e desenho da estampa NÃO
são mancha.

Responda APENAS com JSON válido:
{"sinais_desbotado":"<o que viu, ou 'nenhum'>","desbotado":"sim"|"talvez"|"nao",
 "mancha":"sim"|"nao","mancha_onde":"<foto e lugar, ou ''>","confianca":<0-100>}"""


def usuario(titulo: str) -> str:
    return f'Short Vilebrequin usado. Título do anúncio: "{titulo}". Avalie só o estado de conservação.'
