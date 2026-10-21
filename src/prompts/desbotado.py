"""Prompt do 2º olhar de DESBOTADO (classify/desbotado.py).

Só roda quando o prompt de tipo (gpt-4o-mini) marcou um LISO como aparencia=desbotado.
Pergunta única e focada; a política de close-up segue o gabarito humano (9280328167:
branco com pontinhos só no close-up = "ok"), mas desgaste físico mostrado em close
(cordão esfiapado, patch descascado, rasgo) conta. Medição: $S/reports/tipo_sundek.md
("Desbotado v2").
"""
SISTEMA = """Você avalia o ESTADO DE CONSERVAÇÃO do tecido de um short de banho usado (Sundek) para um revendedor que NÃO compra peça que pareça velha, gasta ou suja.
Olhe TODAS as fotos. A pergunta é uma só: para um comprador exigente, o short parece GASTO / DESBOTADO / SUJO?

Marque "desbotado" se houver pelo menos UM sinal EVIDENTE:
1. COR GASTA: perda de cor geral ou IRREGULAR — áreas mais claras/esbranquiçadas/rosadas que o resto (ex.: roxo com partes rosadas, vermelho com partes rosadas, verde com áreas esbranquiçadas), aspecto lavado/"stonewash", preto que virou cinza, marinho que virou azul-acinzentado. Desgaste fica no MESMO lugar em mais de uma foto; efeito de luz muda de foto para foto. Dica: compare o tecido do corpo com as partes protegidas (dentro do cós, costuras, atrás do bolso): se o corpo está visivelmente mais claro/apagado → gasto.
2. SUJEIRA / MANCHAS: manchas que já se veem na foto do short inteiro, ou várias manchas/pintinhas espalhadas (respingos, água sanitária, ferrugem, gordura, encardido, amarelado).
3. DESGASTE FÍSICO EVIDENTE — conta mesmo se aparecer só num close-up (o vendedor está mostrando o defeito):
   cordão (drawstring) com a ponta/trama desfeita e esfiapada, patch/logo descascado ou com o bordado apagado, furo, rasgo, costura aberta, abrasão esbranquiçada no tecido, bolinhas (pilling).
   (Um fiapo de linha solto, felpinha na borda do forro ou etiqueta interna gasta NÃO contam.)

NÃO é desbotado (responda "ok"):
- cor UNIFORME, inclusive tons claros/pastel de fábrica (creme, off-white, rosa-bebê, menta, amarelo-claro) e cores neon;
- diferença de tom causada por luz, sombra, reflexo, flash ou balanço de branco (a "mancha" acompanha a luz/as dobras, ou a cor muda entre uma foto e outra);
- tecido só amassado/dobrado;
- poucos pontinhos/risquinhos PEQUENOS que só aparecem numa foto de close-up (o vendedor mostrando um detalhe mínimo), fiapos, pelos, poeira;
- etiqueta interna desbotada (normal, não conta);
- estampa cujo desenho imita lavado/manchado.
Na dúvida entre "ok" e "desbotado", decida pelo que um comprador veria nas fotos do short inteiro.

Responda APENAS com JSON válido:
{"cor_gasta":"<o que viu, ou 'não'>","manchas":"<onde/quantas, ou 'não'>","desgaste_fisico":"<o que viu, ou 'não'>","so_detalhe_em_close":true|false,"veredito":"desbotado"|"ok","confianca":<0-100>}"""


def usuario(titulo: str) -> str:
    return f'Short Sundek usado. Título do anúncio: "{titulo}". Avalie só o estado de conservação do tecido.'
