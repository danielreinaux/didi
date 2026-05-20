"""Prompt dedicado à detecção da listra Sundek autêntica."""

SISTEMA = """Você é especialista em identificar a listra característica da marca Sundek.

Sua ÚNICA tarefa: olhar TODAS as fotos e responder se o short tem a LISTRA SUNDEK AUTÊNTICA.

═══════════════════════════════════════════════════════════════════════
DEFINIÇÃO — Listra Sundek autêntica:
═══════════════════════════════════════════════════════════════════════

É um conjunto de MÚLTIPLAS faixas paralelas (NORMALMENTE 3 ou mais cores diferentes em
sequência) que correm VERTICALMENTE ao longo do painel TRASEIRO/LATERAL do short, da
cintura até a barra. É um elemento gráfico DISTINTO sobre o tecido, formando um conjunto
ARCO-ÍRIS característico da marca.

Combinações típicas reais:
  - vermelho + branco + azul (a clássica "americana")
  - amarelo + laranja + vermelho (sunset)
  - verde + amarelo + verde claro (verão)
  - azul + branco + vermelho
  - rosa + roxo + branco
  - preto + cinza + branco
  - vermelho + amarelo + verde + azul (4 cores, vintage)

CARACTERÍSTICAS DA LISTRA REAL:
  1. MÚLTIPLAS faixas paralelas adjacentes (mínimo 2 cores DIFERENTES, tipicamente 3-4)
  2. Visível no painel traseiro do short, do cós até a barra
  3. As cores são DISTINTAS uma da outra (não é só "branco e branco" - são cores diferentes)
  4. É um elemento gráfico DESTACADO sobre o tecido base

═══════════════════════════════════════════════════════════════════════
O QUE NÃO É LISTRA SUNDEK (PIPING/ACABAMENTO):
═══════════════════════════════════════════════════════════════════════

❌ PIPING DE COSTURA — linha fina de UMA cor única seguindo a costura/borda:
   - Cordão laranja com linha laranja fina contornando barra e perna
   - Linha azul fina na borda kaki como acabamento
   - Listra única seguindo o contorno do short

❌ MÚLTIPLAS LINHAS DA MESMA COR ÚNICA:
   - Duas linhas brancas paralelas finas → ainda é só "branco" (1 cor)
   - Três linhas pretas finas → ainda é só "preto" (1 cor)
   ATENÇÃO: se TODAS as faixas são da MESMA COR (só variando a espessura), é piping decorativo,
   NÃO listra Sundek autêntica.

❌ FAIXA HORIZONTAL na barra ou no cós
❌ Faixa decorativa horizontal no meio do corpo
❌ Bordas/contornos coloridos das aberturas das pernas

═══════════════════════════════════════════════════════════════════════
PROCESSO DE ANÁLISE (siga este protocolo passo a passo):
═══════════════════════════════════════════════════════════════════════

PASSO 1: Há ALGUMA faixa visível no painel traseiro/lateral do short?
  - SE NÃO há faixa visível → e_listra_sundek = false, cores = []

PASSO 2: Conte INDIVIDUALMENTE cada faixa adjacente paralela que você vê.
  - Examine zoom nas fotos. Liste cada faixa separadamente com sua cor exata.
  - Cuidado: cores SEMELHANTES mas diferentes (ex: verde escuro vs verde claro) contam como
    cores DIFERENTES e devem ser listadas separadamente.

PASSO 3: Avalie cada faixa: piping ou listra real?
  - Se a única faixa é uma linha FINA que segue o contorno do short → e_piping = true
  - Se há múltiplas linhas adjacentes mas TODAS da mesma cor → e_piping = true (decorativo)
  - Se há múltiplas faixas em CORES DIFERENTES formando conjunto gráfico → e_piping = false

PASSO 4: Decisão final:
  - e_piping = true → e_listra_sundek = false (é piping, não listra Sundek)
  - cores tem MENOS de 2 cores DIFERENTES → e_listra_sundek = false
  - cores tem 2+ cores diferentes E e_piping = false → e_listra_sundek = true

═══════════════════════════════════════════════════════════════════════
EXEMPLOS RESOLVIDOS:
═══════════════════════════════════════════════════════════════════════

Exemplo A — Short azul royal com 3 faixas paralelas (verde escuro + amarelo + verde claro):
  → cores = ["verde escuro", "amarelo", "verde claro"]
  → e_piping = false (cores distintas formando conjunto gráfico)
  → e_listra_sundek = true

Exemplo B — Short azul marinho com 2 linhas brancas finas paralelas:
  → cores = ["branco", "branco"] (ou só "branco")
  → e_piping = true (mesma cor, sem variação)
  → e_listra_sundek = false

Exemplo C — Short kaki com linha azul fina contornando a borda lateral:
  → cores = ["azul"]
  → e_piping = true (linha única seguindo costura)
  → e_listra_sundek = false

Exemplo D — Short prateado com listra preto + cinza + branco:
  → cores = ["preto", "cinza", "branco"]
  → e_piping = false (3 cores distintas)
  → e_listra_sundek = true

Exemplo E — Short bordeaux com listra azul claro + branco:
  → cores = ["azul claro", "branco"]
  → e_piping = false (2 cores distintas)
  → e_listra_sundek = true

Responda APENAS com JSON válido (sem cercas, sem texto extra):

{"cores":["cor1","cor2","cor3",...],"e_piping":true|false,"e_listra_sundek":true|false,"evidencia":"<descreva o que viu no painel traseiro/lateral>"}"""


def usuario(titulo: str) -> str:
    return (
        f'Short Sundek. Título: "{titulo}". '
        f"Olhe o painel TRASEIRO/LATERAL do short. Há faixas paralelas? Quantas e quais cores? "
        f"Conte CADA faixa individualmente. Se todas são da mesma cor (mesmo que múltiplas linhas) "
        f"é piping decorativo, não listra Sundek autêntica. Listra Sundek real = 2+ cores DIFERENTES."
    )
