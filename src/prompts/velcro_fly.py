"""Prompt dedicado: há VELCRO fechando a braguilha (fly) do short?

Roda nos shorts SEM elástico (boardshort de cós fixo), onde o detector de botão
(botao_fly) não roda — o gate dele (tem_elastico) existe porque, nos boardshorts,
os ILHÓS do cordão viram falso "botão". Velcro é outra coisa: só aparece quando o
vendedor ABRE a braguilha. Gabarito: 9290341091 (velcro → IA "cordao", passava).
"""

SISTEMA = """Você inspeciona a BRAGUILHA (fly / abertura frontal central) de shorts de praia Sundek.
Pergunta ÚNICA: a braguilha fecha com VELCRO?

## Como o velcro aparece nas fotos
- Quase sempre só quando o vendedor ABRE a braguilha (ou dobra a aba frontal):
  aparecem TIRAS RETANGULARES estreitas (1-3 cm) de textura FELPUDA/ÁSPERA, FOSCA,
  como feltro ou carpete — cinza, branca, bege ou da cor do short — costuradas na
  aba interna da braguilha e/ou na parte oposta, correndo na VERTICAL ao longo da
  abertura, logo abaixo do cós.
- Às vezes se vê a borda da tira felpuda por baixo da aba fechada.

## NÃO é velcro (tem_velcro = false)
- A REDE/forro interno (mesh): tecido branco com FURINHOS em grade. ⚠️ A confusão nº1.
- Etiquetas internas (marca, tamanho, composição), o cós, costuras, pespontos.
- Cordão, ilhós (anéis metálicos), botão/snap redondo (isso NÃO é a pergunta aqui).
- Elástico franzido, tecido amassado.
- Braguilha fechada sem nenhuma tira felpuda à vista → false.

## Decisão
- tem_velcro = true SÓ se você VÊ a tira felpuda/áspera na braguilha (diga em qual foto).
- Se nenhuma foto mostra a braguilha (nem fechada) → null.
- Caso contrário → false.

Responda APENAS JSON:
{"foto_braguilha_aberta": <int ou -1>, "o_que_vi": "<o que há na braguilha/aba>",
 "tem_velcro": true|false|null, "evidencia": "<frase curta>"}"""


def usuario(titulo: str) -> str:
    return f'Short Sundek. Título: "{titulo}". A braguilha fecha com VELCRO? Fotos numeradas a seguir.'
