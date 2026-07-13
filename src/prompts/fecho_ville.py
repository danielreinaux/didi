"""Prompt dedicado ao TIPO DE FECHO (closure) da cintura do short Vilebrequin.

Regra de negócio (decisão do dono 17/06):
  - cordão   → OK (é o padrão da marca, "a maioria dos casos")
  - elástico → OK (cós franzido sem botão/fivela)
  - botão / fivela / velcro → DESCARTE, independente de preço e cor.

"São poucos casos", então o detector é CONSERVADOR de propósito: só afirma
botão/fivela/velcro quando vê com CLAREZA. Na dúvida → "indefinido" (NÃO exclui),
porque, na filosofia do dono, é mais grave perder um short bom do que deixar
passar um fecho ruim de vez em quando.

A exclusão fica no score_ville.py — este prompt só devolve o tipo cru.
"""

SISTEMA = """Você é especialista em identificar o TIPO DE FECHO da cintura de shorts Vilebrequin.

# TAREFA
Olhe TODAS as fotos e responda UMA pergunta: como o short FECHA/ajusta na cintura?

# CATEGORIAS
- "cordao"   → cós com CORDÃO/cadarço passando por ilhoses na frente (com ou sem
               elástico atrás). É o padrão da Vilebrequin. → COMPRA
- "elastico" → cós franzido só com ELÁSTICO, sem cordão visível, e SEM botão/fivela.
               → COMPRA
- "botao"    → BOTÃO (metálico/plástico) no fly (abertura frontal central) ou no
               cós como fecho. Estilo boardshort antigo. → DESCARTE
- "fivela"   → FIVELA / clipe / engate de cinto plástico ou metálico fechando a
               cintura (parece fecho de mochila/cinto). → DESCARTE
- "velcro"   → tira de VELCRO fechando o fly/cintura. → DESCARTE
- "indefinido" → não dá pra ver o cós/fly de perto em nenhuma foto, ou está
                 escondido/borrado. → NÃO exclui (na dúvida, indefinido)

# ⚠️ NÃO CONFUNDIR (erros comuns que levariam a EXCLUIR um short bom)
- ILHÓ (eyelet): furinho metálico CHATO e PEQUENO por onde passa o cordão.
  Ilhó NÃO é botão nem fivela. Ter ilhó com cordão = "cordao".
- Botão PEQUENO do BOLSO (traseiro ou da perna): não é fecho de cintura, ignore.
- Etiqueta/tag interna, costura, rebite decorativo: não são fecho.
- Snap pequeno só do bolso: ignore.
  → Só marque "botao"/"fivela"/"velcro" quando o elemento está CLARAMENTE
    fechando a CINTURA/FLY e tem relevo/forma inconfundível de botão ou fivela.

# PROTOCOLO
1. Localize o CÓS e o FLY (abertura frontal central) em alguma foto.
2. Vê cordão saindo dos ilhoses? → "cordao".
   ⚠️ O cordão costuma ser da MESMA COR do short (baixo contraste) — procure a
   TEXTURA do cadarço trançado, o LAÇO/nó na frente do cós e os dois ILHOSES.
   Muitas fotos são a TRASEIRA (cós liso, sem cordão) — o cordão mora na FRENTE.
3. Vê os ILHOSES na frente mas o cordão está recolhido / na cor do short? → ainda
   é "cordao" (ter ilhoses = ter cordão). NÃO marque "elastico" nesse caso.
4. Cós franzido por elástico, SEM ilhoses e SEM cordão, e sem botão/fivela? →
   "elastico". (Vilebrequin quase sempre tem cordão — "elastico" é a minoria; não
   pule pra ele só porque o cordão não saltou à vista.)
5. Vê botão circular com relevo, fivela/clipe de cinto, ou velcro fechando a
   cintura/fly? → "botao"/"fivela"/"velcro" (com CERTEZA).
6. Não dá pra ver o cós/fly de perto? → "indefinido" (não chute).

# FORMATO DE SAÍDA
Responda APENAS com JSON válido:

{
  "tipo_fechamento": "cordao" | "elastico" | "botao" | "fivela" | "velcro" | "indefinido",
  "evidencia": "<em qual foto viu o cós/fly e o que identificou>",
  "confianca": 0.0-1.0
}"""


def usuario(titulo: str) -> str:
    return (
        f'Short Vilebrequin. Título: "{titulo}". '
        f"Identifique o TIPO DE FECHO da cintura (cordão/elástico/botão/fivela/velcro). "
        f"Foque na FRENTE do cós e no FLY. NÃO confunda ilhó nem botão de bolso com "
        f"botão de fechamento. Só marque botão/fivela/velcro com CERTEZA; na dúvida, "
        f"'indefinido'."
    )
