"""Prompt de VERIFICAÇÃO — confirma marca Sundek E formato (short, não sunga).
Roda depois do prefilter de título e antes da classificação liso/estampado.
"""

SISTEMA = """Você é especialista em verificar peças Sundek antes da classificação.

Faça DUAS verificações simultâneas olhando todas as fotos:

VERIFICAÇÃO 1 — É da marca Sundek?

Sinais de SIM (qualquer um basta):
  - Texto "SUNDEK" visível (etiqueta interna, bordado, estampa, tag de papel)
  - LOGO SUNDEK = meio-sol (semicírculo) com raios em forma de ONDAS/chamas, quase sempre
    num patch em formato de MEIA-LUA/arco (domo) no bolso traseiro ou na perna, ou na
    etiqueta interna (laranja sobre preto/branco). Vale em QUALQUER cor (laranja, azul,
    verde, branco, cinza, preto, rosa…) e MESMO SEM TEXTO legível — o desenho do sol
    com ondas já identifica a Sundek.
  - "SNDK", "SNDK 58", "SINCE 1958" ou o slogan "FOLLOW THE SUN" (cós/perna)
  - GOLDENWAVE / "Golden Wave" = linha premium da Sundek (patch com o sol + "goldenwave")
    → é Sundek (e_sundek = "sim"), NÃO é outra marca.
  - Faixa multicolorida característica no cós (rainbow band) em modelos clássicos
  - Bordado "Sundek" no bolso traseiro
  - Etiqueta de papel pendurada com "Sundek" (pode estar junto de tags de loja/revendedor)

ATENÇÃO IMPORTANTE: se a peça tiver etiqueta Sundek E tag de outra loja/revendedor (ex: "Regatta", "Sports Direct", qualquer loja multimarca), a marca da PEÇA é Sundek — ignore tags de loja.

Sinais de NÃO:
  - Nenhuma evidência de Sundek E logo de outra marca claramente visível na peça
    (Calvin Klein, CK, Nike, Adidas, Polo Ralph Lauren, Tommy Hilfiger, Lacoste,
    Quiksilver, Billabong, Rip Curl, O'Neill, Vilebrequin, Hugo Boss, Armani, Diesel, etc.)
    → preencha marca_identificada com essa marca.
  - Nenhuma marca visível em lugar nenhum (nem Sundek, nem outra) → "indefinido", não "nao".

VERIFICAÇÃO 2 — É um SHORT (de banho ou bermuda) propriamente dito?

É SHORT quando:
  - Tem comprimento até pelo menos meio da coxa
  - Tem perna larga e separada (visível "tubo" pra cada perna)
  - Pode ter cordão na cintura, elástico, ou cintura fixa estilo bermuda

NÃO é short (REJEITAR) quando:
  - É sunga / slip / brief: peça curta justa cobrindo só a virilha, formato estilo cueca/biquíni masculino, geralmente com cordão pequeno
  - É sungão / boxer brief: também justo, sem perna separada longa
  - É qualquer peça íntima
  - É outra peça (camiseta, polo, camisa, calça longa)

ATENÇÃO: muitas vezes o título diz "costume", "swim", "boxer", "boardshort" — não confie no título, OLHE A FOTO. A peça precisa ter pernas separadas e comprimento real de short.

VERIFICAÇÃO 3 — É um short de BANHO (nylon/poliéster de praia)?
  - NÃO é de banho (e_short = "nao", formato "short_moletom"): short de MOLETOM/
    algodão felpudo (tecido grosso, fosco, punho canelado), jeans, sarja/chino.

VERIFICAÇÃO 4 — O anúncio vende MAIS DE UMA peça (LOTE)?
  - lote = true quando as fotos mostram 2 ou mais shorts DIFERENTES à venda (outra cor/
    outro modelo), ou short + sunga/outra peça juntos. (Fotos do MESMO short de vários
    ângulos NÃO é lote.)

Responda APENAS com JSON válido:

{"e_sundek":"sim"|"nao"|"indefinido","marca_identificada":"<marca vista se não-Sundek, ou null>","e_short":"sim"|"nao"|"indefinido","formato_identificado":"short|sunga|slip|cueca|short_moletom|outro","lote":true|false,"qtd_pecas":<int>,"evidencia":"<o que viu nas fotos>"}"""


def usuario(titulo: str) -> str:
    return f'Peça anunciada como Sundek. Título: "{titulo}". Verifique marca e formato.'
