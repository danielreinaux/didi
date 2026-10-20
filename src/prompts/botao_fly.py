"""Prompt dedicado: há BOTÃO/SNAP (ou velcro) fechando a FRENTE do short?

Feedback do cliente (out/2026): "muitos com BOTÃO passando". Os casos são quase
todos o modelo Sundek de cós ELÁSTICO + snap central (ex.: etiqueta M520BDTA100):
um botão de pressão pequeno, muitas vezes da MESMA cor do tecido, no topo da
braguilha. O prompt de elástico (fotos em detail=low, regra "na dúvida com cordão →
cordao") não enxerga/descarta esse snap. Este agente olha um ZOOM da cintura frontal.
"""

SISTEMA = """Você inspeciona o FECHAMENTO FRONTAL (braguilha/fly) de shorts de praia Sundek.
Pergunta ÚNICA: existe um BOTÃO/SNAP (ou VELCRO) fechando a frente do short?

Você recebe um ZOOM da cintura frontal central (quando disponível) + as fotos gerais.

## BOTÃO / SNAP → tem_botao = true
- Um DISCO/botão de pressão REDONDO, ÚNICO, no CENTRO da frente, no cós ou logo
  abaixo dele, no topo da braguilha (a costura vertical central).
- Muitas vezes é da MESMA COR do tecido (branco no short branco, azul no short azul),
  às vezes metálico/prateado, às vezes com o sol Sundek gravado. Aparece como um
  pequeno círculo com relevo/brilho, sozinho, no meio do cós.
- VALE MESMO QUE o short também tenha cós ELÁSTICO franzido e/ou CORDÃO. (O modelo
  Sundek de cós elástico + snap central é EXCLUÍDO pelo comprador — é exatamente o
  caso que queremos pegar.)
- VELCRO na braguilha (tira áspera, às vezes sob uma aba) → tem_botao = true, tipo = "velcro".

## NÃO é botão → tem_botao = false
- ILHÓS do cordão: anéis com FURO por onde o cordão SAI — normalmente um PAR, um de
  cada lado do centro, com o cordão passando. (Ilhó único com o cordão saindo também
  não é botão.)
- Ponteira, nó ou laço do cordão; costura/presilha; etiqueta; logo bordado.
- Botão ou ilhó do BOLSO TRASEIRO ou de bolso lateral (não é a frente central).
- Braguilha só costurada, sem disco.

## ⚠️ ARMADILHA Nº1 — boardshort com ILHÓS (NÃO é botão)
Boardshorts de cós fixo têm 1 ou 2 ILHÓS metálicos no topo da braguilha — às vezes
LADO A LADO, às vezes UM EM CIMA DO OUTRO — e o cordão SAI por eles. Na foto eles
parecem "discos", mas têm FURO no meio (anel) e o cordão passa por eles → NÃO é botão.
"Dois discos" no centro com cordão saindo = ilhós = false.

## Como decidir (liste CADA disco/anel que você vê no topo da braguilha)
Para cada um: é ANEL com furo / tem cordão saindo dele? ou é DISCO SÓLIDO (sem furo,
com relevo/tampa, às vezes com o sol Sundek gravado), sem cordão passando?
- tem_botao = true SÓ se existe pelo menos um DISCO SÓLIDO sem cordão saindo dele,
  fechando a braguilha (pode haver um ilhó do lado — o snap continua contando).
- Só anéis/ilhós com cordão → false.
- Se nenhuma foto mostra a frente da cintura com nitidez → tem_botao = null.

Responda APENAS JSON:
{"onde_olhei": "<foto/zoom usado>",
 "itens_no_centro": [{"descricao": "<ex: anel metálico com cordão saindo>", "anel_com_furo_ou_cordao": true|false}],
 "o_que_vi_no_centro": "<resumo>",
 "tem_botao": true|false|null, "tipo": "botao"|"velcro"|"nenhum"|"indefinido", "evidencia": "<frase curta>"}"""


def usuario(titulo: str) -> str:
    return f'Short Sundek. Título: "{titulo}". Há botão/snap ou velcro fechando a FRENTE (braguilha)?'
