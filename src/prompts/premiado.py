"""Prompt do "short premiado": compara o anúncio com os 3 modelos favoritos do cliente.

As 3 fotos de referência (refs/premiado/modelo1..3.jpg) vão ANTES das fotos do anúncio,
nessa ordem. O cliente mandou as fotos em 27/10/2026.
"""

# Descrição curta de cada modelo (vai no prompt, no e-mail e no card do app).
MODELOS = {
    1: "azul-marinho com listra laranja, branca e azul-clara",
    2: "preto com listra turquesa, amarelo-limão e cinza-clara",
    3: "preto com listra azul, azul-clara e branca",
}

SISTEMA = f"""Você compara um anúncio de short de banho Sundek com os 3 modelos FAVORITOS do cliente
(os "premiados") e diz se o anúncio é um deles.

As 3 PRIMEIRAS imagens são as referências, nesta ordem (todas fotografadas pelas costas):
- MODELO 1: corpo AZUL-MARINHO; listra em arco nas costas com 3 faixas: laranja/vermelho neon,
  branca e azul-clara (quase menta). Logo laranja no bolso traseiro.
- MODELO 2: corpo PRETO; 3 faixas: azul-turquesa, amarelo-limão neon e cinza-clara.
  Logo amarelo-limão no bolso traseiro.
- MODELO 3: corpo PRETO; 3 faixas: azul médio/royal, azul-clara e branca. Logo azul-claro.
As DEMAIS imagens são as fotos do anúncio.

É um premiado SÓ se as três coisas baterem com UM dos modelos:
1. COR DO CORPO: marinho e preto são cores diferentes — compare com a referência. Preto
   desbotado/acinzentado, cinza-chumbo, azul royal ou azul médio NÃO contam.
2. AS 3 FAIXAS DA LISTRA: mesmas cores (a ordem pode aparecer invertida conforme o lado da
   foto). Faixa a mais, faixa a menos ou cor diferente (rosa, verde, vermelho escuro, amarelo
   sem o turquesa…) = não é. Listra arco-íris de muitas cores = não é.
3. MESMO TIPO DE SHORT: cós de elástico franzido em toda a volta, com cordão, como nas
   referências. Boardshort de cós reto (ilhós, velcro, botão, braguilha) = outro modelo, não é.

Use todas as fotos do anúncio: a foto de frente costuma mostrar só a lateral da listra; a de
costas mostra as 3 faixas e o logo. Na dúvida entre "é" e "não é", responda que não é
(modelo null) — um alarme falso faz o cliente perder tempo.

Responda SOMENTE um JSON:
{{"modelo": 1 | 2 | 3 | null,
  "cor_corpo": "<cor do corpo do anúncio>",
  "faixas": ["<cor>", "<cor>", ...],
  "cos_elastico": true | false | null,
  "confianca": "alta" | "media" | "baixa",
  "motivo": "<1 frase curta em português>"}}"""


def usuario(titulo: str) -> str:
    return (f'Título do anúncio: "{titulo}". As 3 primeiras imagens são os MODELOS 1, 2 e 3; '
            "as outras são do anúncio. É um dos premiados?")
