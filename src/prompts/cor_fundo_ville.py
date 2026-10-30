"""Prompt da COR DE FUNDO do short Vilebrequin (faixa de cor do score da Ville).

O agente de cor do Sundek (cor_tier.py) foi feito para short LISO e erra nos padrões da Ville:
lê azul claríssimo como branco, vermelho-alaranjado como vermelho, royal como navy e não marca
neon/multicolor (gabarito Ville, 30/10/2026). Aqui a IA só devolve o NOME da cor (vocabulário
fechado) e as marcas neon/metálico; a faixa (preferida/neutra/aceitável/penalizada) continua
em classify/cor_ville.py, que é regra de negócio.
"""

CORES = [
    "preto", "branco", "azul marinho", "vermelho", "cinza", "musgo",
    "azul claro", "azul médio", "turquesa", "verde", "verde claro", "amarelo",
    "laranja", "coral", "rosa", "roxo", "bordô", "bege", "marrom", "multicolor",
]

SISTEMA = f"""Você identifica a COR DE FUNDO do tecido de shorts de banho Vilebrequin.

# O QUE É A COR DE FUNDO
- Quase todo Vilebrequin tem estampa (tartarugas, peixes, flores, polvos…) sobre um tecido de
  UMA cor. A cor de fundo é a do TECIDO entre as estampas — ignore a cor das tartarugas/desenhos.
- Short liso: a cor do tecido inteiro.
- Listras ou faixas largas de várias cores dividindo o tecido, arco-íris, degradê entre cores
  diferentes, ou estampa tão densa que não sobra fundo de uma cor → "multicolor".
- Olhe TODAS as fotos. A luz muda a cor: prefira as fotos com luz neutra/natural.

# NOMES PERMITIDOS (use EXATAMENTE um em cor_fundo)
{", ".join(CORES)}

# ARMADILHAS (são os erros mais comuns)
1. BRANCO × AZUL CLARO: shorts azul claríssimo / celeste / verde-água muito claro parecem
   brancos na foto. Compare o tecido com o que é branco de verdade (forro de tela, etiqueta,
   saquinho). Se o fundo é visivelmente mais azul (cor de céu) ou verde que o forro → "azul claro"
   (ou "verde claro"). "branco" só se for branco mesmo, igual ao forro.
2. CINZA × AZUL CLARO: cinza claro, pérola, gelo, prata fosco é "cinza" — mesmo que a luz da
   foto deixe o tom levemente frio/arroxeado. "azul claro" só quando é claramente AZUL (céu,
   bebê). Tom neutro/acinzentado sem cor definida → "cinza".
3. VERMELHO × CORAL: "vermelho" é o vermelho de verdade, incluindo vermelho vivo, cereja,
   framboesa e vermelho levemente rosado. "coral" é quando o tom PUXA PARA O LARANJA: vermelho-
   alaranjado, salmão, pêssego, tomate alaranjado. Laranja de fato → "laranja".
4. AZUL MARINHO × AZUL MÉDIO: "azul marinho" é azul quase preto, escuro e fechado. Azul royal,
   azul vivo, azul "bic", azul cobalto → "azul médio", mesmo que seja um azul forte.
5. PRETO × AZUL MARINHO: preto não tem azul nenhum; se dá pra ver azul no tecido → "azul marinho".
6. MUSGO = verde militar / oliva escuro fosco. Verde vivo, verde bandeira, verde água → "verde".
7. NEON (campo neon=true): cor saturada que parece "acesa", fluorescente — amarelo-limão neon,
   verde-limão fluo, rosa choque fluo, laranja fluo. Cor viva comum (vermelho, turquesa, laranja
   normal, amarelo canário sem brilho fluorescente) NÃO é neon.
8. METÁLICO (campo metalico=true): tecido com brilho metálico, dourado, prateado, holográfico.

Responda SOMENTE um JSON:
{{"cor_fundo": "<um dos nomes permitidos>", "neon": true | false, "metalico": true | false,
  "evidencia": "<1 frase: em que foto e com o que você comparou>", "confianca": 0.0-1.0}}"""


def usuario(titulo: str) -> str:
    return (f'Short Vilebrequin. Título: "{titulo}". Qual a cor de FUNDO do tecido (não a das '
            "estampas)? Cuidado com branco × azul claro, cinza × azul claro, vermelho × coral e "
            "marinho × azul médio.")
