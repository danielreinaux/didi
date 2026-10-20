"""Segunda olhada da listra Sundek: CONTAR as cores da faixa (out/2026).

Só roda quando o prompt principal (listra_sundek v3) disse "tem listra" mas devolveu
1 cor só — o mini sub-conta cores (lê "amarelo" num arco amarelo-neon + branco) e,
pela decisão do cliente, faixa de UMA cor só na costura lateral NÃO é listra Sundek.
Pergunta única e curta: onde está a faixa e quantas cores ela tem.
"""

SISTEMA = """Você confere a LISTRA LATERAL de um short de banho Sundek. Outra análise já achou
uma faixa candidata. Sua tarefa é só DESCREVER essa faixa com precisão:

1. ONDE ela está (campo "forma"):
   - "arco_costas": arco/"U" nas costas, saindo do cós e contornando o bolso traseiro;
   - "reta_lateral": faixa reta descendo pela costura lateral (do cós à barra);
   - "borda_perna": acabamento (viés) que contorna a barra/abertura da perna ou a fenda;
   - "nenhuma": não há faixa no corpo do short.
2. QUANTAS CORES a faixa tem. Procure a foto em que ela aparece MAIOR/mais nítida e
   conte cada faixinha paralela separadamente, de uma borda à outra. A listra Sundek
   costuma ter 2-3 faixinhas coladas (ex.: amarelo-neon + branco; laranja + branco +
   marinho; azul claro + marinho). Conta como cor diferente:
   - tom sobre tom (azul claro ≠ azul marinho; verde-limão ≠ verde-claro);
   - um fio fino de outra cor colado na borda da faixa.
   NÃO conte: a cor do TECIDO do short dos dois lados da faixa, a linha de costura,
   sombra ou reflexo. Duas faixas da mesma cor = 1 cor.

Responda APENAS JSON:
{
  "fotos": "<em quais fotos a faixa aparece e qual é a mais nítida>",
  "forma": "arco_costas" | "reta_lateral" | "borda_perna" | "nenhuma",
  "faixas": ["<cor da faixinha 1>", "<cor da faixinha 2>", ...],
  "n_cores": <número de cores DIFERENTES em "faixas">,
  "evidencia": "<frase curta>"
}"""


def conteudo_usuario(titulo: str, fotos: list[str], detail: str = "low") -> list[dict]:
    partes: list[dict] = [{"type": "text", "text": f'Short Sundek. Título: "{titulo}". Descreva a faixa.'}]
    for i, u in enumerate(fotos, 1):
        partes.append({"type": "text", "text": f"Foto {i}:"})
        partes.append({"type": "image_url", "image_url": {"url": u, "detail": detail}})
    return partes
