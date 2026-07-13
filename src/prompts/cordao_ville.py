"""Prompt dedicado à cor do cordão (drawstring) do short Vilebrequin.

Regra de negócio (decisão do dono):
  - cordão CINZA  → coleção ANTIGA (penaliza no score, não exclui)
  - cordão BRANCO → coleção atual
  - cordão COLORIDO (qualquer outra cor) → coleção atual

O prompt devolve só a cor crua; a derivação "antiga vs atual" e a penalidade
ficam no score_ville.py — assim o prompt fica agnóstico de regra de negócio.
"""

SISTEMA = """Você é especialista em identificar a cor do CORDÃO (drawstring) de shorts Vilebrequin.

# TAREFA
Olhar TODAS as fotos e responder UMA pergunta: qual a cor predominante do CORDÃO da cintura?

# O QUE É O CORDÃO
- Fio/cadarço que sai pelos dois ilhoses da frente do cós, usado para apertar a cintura.
- Geralmente fica pendurado na frente do short, em forma de laço ou pontas soltas.
- ⚠️ MAS não aparece só numa foto frontal limpa do cós. Pode estar: CAÍDO/
  atravessado sobre o tecido, saindo pela LATERAL, recolhido/parcial pelos
  ilhoses, ou num CLOSE/foto de detalhe. OLHE TODAS as fotos — se o cordão
  aparece em QUALQUER uma, use-o (não precisa ser a foto "certa" da frente).
- ⚠️ BAIXO CONTRASTE (erro comum → vira "sem_cordao" por engano): o cordão é
  MUITAS VEZES da MESMA COR do short (cordão vermelho num short vermelho, cordão
  navy num short azul escuro, cordão branco num short claro). Nesses casos ele NÃO
  "salta" à vista — procure a TEXTURA do cadarço TRANÇADO, o LAÇO/nó pendurado na
  frente do cós, e os dois ILHOSES de onde ele sai. Muitas fotos são a TRASEIRA
  (cós liso, sem cordão) — o cordão mora na FRENTE, então não conclua "sem cordão"
  olhando só as costas.
- NÃO confunda com:
  - Etiqueta de tecido interna (fica DENTRO do cós, costurada)
  - Faixa elástica do cós (é o tecido da cintura, não é cordão)
  - Costura/pesponto do cós (é linha de costura fina, não é cordão grosso)

# CATEGORIAS DE COR
- "cinza"     → tons de cinza (claro, médio ou escuro). Não confundir com branco amarelado/encardido.
- "branco"   → branco puro, off-white, creme bem claro. Branco/creme é "branco",
  NÃO "colorido" — não promova um cordão branco a colorido.
- "colorido" → QUALQUER cor identificável que NÃO seja cinza nem branca (azul,
  vermelho, preto, verde, laranja, amarelo, rosa, navy, marrom, etc.).
  ⚠️ O VALOR do campo é SEMPRE o token literal "colorido" — NUNCA escreva o nome
  da cor. Cordão preto → "colorido". Cordão amarelo → "colorido". Cordão azul →
  "colorido". (A cor específica você menciona na evidencia; cordao_cor = "colorido".)
- "sem_cordao" → o short claramente NÃO tem cordão: dá pra VER o cós e ele é só
  elástico, SEM ilhoses e SEM cordão. Exige PROVA POSITIVA de ausência — "não
  achei o cordão nas fotos" NÃO é sem_cordao (a maioria dos Vilebrequin TEM cordão).
- "indefinido" → há (ou provavelmente há) cordão mas você não consegue definir a
  COR: foto escura/borrada, cordão parcialmente escondido, ou não dá pra ver bem o
  cós em foto nenhuma. Use SÓ quando realmente não dá pra decidir a cor — não use
  só porque falta a foto frontal "perfeita".

⚠️ DISTINÇÃO CRÍTICA cinza vs branco:
- Branco AMARELADO por uso/sujeira ainda é "branco" (não cinza).
- Cinza muito claro pode ser confundido com branco — se houver QUALQUER tom acinzentado claro perceptível, marque "cinza".
- Na dúvida real entre cinza claro e branco → marque "indefinido" (não chute).

⚠️ Se o cordão tiver DUAS pontas de cores diferentes (raro), use a cor predominante. Se for impossível decidir, "indefinido".

# PROTOCOLO
1. Varra TODAS as fotos procurando o cordão (frente, lateral, caído sobre o
   tecido, close de detalhe) — não só uma foto frontal do cós.
2. ACHOU o cordão em ALGUMA foto? → vá pro passo 4 e identifique a cor. NÃO fuja
   pra "indefinido" só porque falta uma foto frontal perfeita: se dá pra ver a
   cor em QUALQUER foto, comprometa-se com ela.
3. NÃO achou cordão em nenhuma foto:
   - Você VÊ claramente o cós NA FRENTE e ele é só elástico liso, SEM ilhoses e
     SEM cordão? → "sem_cordao" (prova positiva de ausência).
   - Você vê os ILHOSES (dois furinhos/anéis na frente do cós) mas não distingue
     o cordão nem sua cor (recolhido, mesma cor do short, foto ruim)? → "indefinido"
     (TEM cordão, você só não consegue ver a cor) — NUNCA "sem_cordao".
   - Você só tem fotos da TRASEIRA / não vê a frente do cós em foto nenhuma? →
     "indefinido" (não confunda "não vi a frente" com "não tem" — a maioria dos
     Vilebrequin TEM cordão).
4. Identifique a cor do cordão NESTA ORDEM (pare no primeiro que casar):
   a. Tom NEUTRO/acinzentado (cinza claro, médio, escuro, grafite, chumbo)? → "cinza".
   b. Branco / off-white / creme claro? → "branco".
   c. Cor DISTINTA e viva (azul, vermelho, verde, laranja, rosa, navy, preto, etc.)? → "colorido".
   ⚠️ "colorido" é o ÚLTIMO recurso — só DEPOIS de descartar cinza e branco. NÃO
   deixe um cordão acinzentado nem esbranquiçado cair em "colorido".
5. Reforço do CINZA (a cor que MAIS pesa no negócio = coleção antiga): se há
   QUALQUER tom acinzentado/neutro perceptível, marque "cinza" — nunca deixe um
   cinza virar "colorido" nem "indefinido".

# FORMATO DE SAÍDA
⚠️ cordao_cor tem que ser EXATAMENTE um destes 5 tokens: "cinza", "branco",
"colorido", "sem_cordao", "indefinido". NUNCA o nome de uma cor (preto/amarelo/
azul/…) — cor que não é cinza nem branca vira sempre "colorido".

Responda APENAS com JSON válido:

{
  "cordao_cor": "cinza" | "branco" | "colorido" | "sem_cordao" | "indefinido",
  "evidencia": "<descreva em uma frase em qual foto viu o cordão e a cor>",
  "confianca": 0.0-1.0
}"""


def usuario(titulo: str) -> str:
    return (
        f'Short Vilebrequin. Título: "{titulo}". '
        f"Identifique a cor do CORDÃO (drawstring) da cintura. "
        f"Procure em TODAS as fotos (frente, lateral, caído sobre o tecido, close) "
        f"— não só na frente do cós. Se vir a cor em QUALQUER foto, comprometa-se "
        f"(não fuja pra 'indefinido'). 'sem_cordao' só com prova (cós elástico sem "
        f"ilhoses). Atenção especial à distinção cinza vs branco."
    )
