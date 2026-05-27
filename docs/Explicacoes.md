# Explicações — Didi (Radar Sundek/Vilebrequin)

Documento de referência. Cobre: **o que o sistema faz**, **as regras que ele aplica**, **como o processo funciona internamente** e **quais comandos você pode rodar**.

---

## 1. O que o sistema é

O Didi é um pipeline autônomo que faz três coisas em sequência:

1. **Scrape** do Vinted (catálogo de homens, marca Sundek ou Vilebrequin).
2. **Classificação por IA** (OpenAI Vision — `gpt-4o-mini` para a maioria das checagens, `gpt-4o` em validações finas).
3. **Decisão de compra** — cada item recebe um *score* (0–100) e um veredito: `comprável`, `médio (barganha)` ou `descartado`.

O resultado vai para dois lugares:
- `data/coleta-classificada.json` — fonte de verdade do pipeline.
- `votacao/public/items.json` — alimenta a UI de votação onde o usuário dá feedback.

E para visualizar:
- `data/analise.html` — auditoria completa, agrupada por motivo de exclusão.
- `data/funil.html`, `data/diagnostico.html`, `data/visualizar.html` — outras visões.

---

## 2. Regras que o sistema analisa

As regras vêm do manual `docs/Regras_Compra_Shorts-4.docx` + histórico real de 380 compras Sundek.

### 2.1 Filtros de catálogo (antes da IA)
- **Marca:** Sundek (ID Vinted `36501`) ou Vilebrequin (ID `99810`).
- **Preço:** Sundek €1–€45; Vilebrequin €40–€100.
- **Tamanhos aceitos:** S, M, L, XL, ou numéricos 29–34.
- **Estado:** novo, novo sem etiqueta, muito bom, bom.

### 2.2 Prefilter de título (regex, sem IA)
Descarta por palavras-chave: `polo`, `t-shirt`, `camiseta`, `sunga`, `slip`, `calça`, `bambino`, `taille X ans`, etc. Também filtra tamanhos numéricos fora de 29–34.

### 2.3 Tipo do short (IA — `gpt-4o-mini`)
Classifica em: `liso` · `estampado` · `logo_grande` · `desbotado` · `indefinido`.
- **Liso** → único candidato a comprável (segue o pipeline).
- **Estampado / Logo gigante / Desbotado** → descartado.
- Detecta também `bicolor` (dois painéis grandes), `tecido_brilhoso` (wet look) e `tem_listra_lateral_sundek` (presença das listras laterais).

### 2.4 Tier de cor (IA — `gpt-4o-mini`, só em lisos)
Cinco tiers, definidos no histórico de compras (`src/prompts/cor_tier.py`):

| Tier | Cores | Comentário |
|---|---|---|
| `maravilhoso` | Preto, Branco, Azul marinho/escuro/navy | Elite — vendem sozinhos |
| `muito_boa` | Cinza (qualquer tom, **fosco**) | 19% das compras históricas |
| `boa` | Azul médio/royal/cobalto, verde militar/oliva, kaki escuro | Alta liquidez |
| `ok` | Azul claro, turquesa, verde médio, laranja terroso, salmão, coral, vermelho médio, vinho, bege, mostarda, fucsia (não-fluo) | Aceitável; depende de outros atributos |
| `ruim` | Cores **NEON/FLUO** verdadeiras, tecido **metálico/brilhoso**, roxo gritante, vermelho-tomate puro | Excluído |

**Regra anti-falso-positivo:** cor viva ≠ cor neon. `ruim` só vale se a cor parece *brilhar como marca-texto*, ou se o tecido tem aspecto satin/espelhado, ou se é roxo/tomate gritante puro.

### 2.5 Listra Sundek (IA — `gpt-4o`)
Verifica a listra lateral arco-íris autêntica. Distingue de **piping** (acabamento de costura). Captura também as cores das listras para a regra de combinação.

### 2.6 Combinação Cor + Listras (`src/utils/listra_tier.py`)
- Listras **neutras** (azul, branco, cinza, preto) podem **salvar** uma cor `ok` (laranja, coral, salmão, verde, fucsia) e subi-la a `boa`.
- Listras **raras** (roxa, dourada, rosa) **penalizam** cores `ok`/`boa`.
- Cores **absolutamente ruins** (amarelo, vermelho médio, roxo, verde-limão, rosa) **não são salvas** por listra nenhuma.
- O resultado vira `cor.tier_final` (≠ `cor.tier` puro da IA).

### 2.7 Elástico + Fechamento (IA — `gpt-4o`)
Detecta: cintura **elástica** (esperado) ou **botão/velcro** (boardshort antigo — descartado).
Short sem elástico perde 15 pts no score.

### 2.8 Bolso traseiro (IA — `gpt-4o`)
- **Sem bolso traseiro** → descartado.
- **Bolso com nome `SUNDEK` bordado** → ✓.
- **Bolso só com logo (sem nome)** → coleção antiga, descartado.
- **Bolso frontal/cargo** → descartado.

### 2.9 Etiqueta de cintura (IA — `gpt-4o-mini`)
Etiqueta bordada na cintura interna dá bônus de +10 pts e +€4 no teto de preço.

### 2.10 Filtros de exclusão final (no `score.py`)
Causam descarte direto (score = 0):
`estampado`, `logo_grande`, `nao_sundek`, `nao_short`, `tamanho_invalido`, `infantil`, `desbotado`, `cor_ruim`, `tecido_brilhoso`, `bicolor`, `fechamento_botao`, `fechamento_velcro`, `bolso_frontal`, `listra_na_frente`, `sem_bolso_traseiro`, `bolso_so_logo_colecao_antiga`, `sem_listra_sundek`, `piping_nao_e_listra_sundek`, `tamanho_XS`, `tamanho_XXL`, `tamanho_numerico_fora_de_31-34`.

---

## 3. Sistema de score

Cada item recebe `score 0–100` = **atributos (0–70)** + **eficiência de preço (0–30)**.

### Pontos de atributo
| Critério | Pontos |
|---|---|
| Tier maravilhoso / muito_boa / boa / ok / ruim | +30 / +22 / +15 / +8 / 0 |
| Tamanho M / L / XL / S | +20 / +16 / +8 / +4 |
| Tem elástico | +15 |
| **Sem** elástico | **−15** |
| Etiqueta na cintura | +10 |
| Listra salva a cor | +5 |

### Eficiência de preço
Define um **teto** em € por tier (e ajusta por tamanho/elástico/etiqueta). Compara preço real ao teto:
- preço ≤ 50% do teto → +30 pts
- 50–70% → +20
- 70–90% → +10
- 90–100% → +5
- acima do teto × 1.25 → **descartado**

### Decisão final
- `score ≥ 70` → **comprável**
- `45 ≤ score < 70` → **médio (tenta barganha)**
- `score < 45` → **descartado**

**Override:** elástico + preço ≤ €9 + cor boa = sempre comprável.

---

## 4. Como o processo funciona (agentes)

O pipeline é orquestrado em `src/classify/run.py`. Cada item passa por estes "agentes" (na ordem; se um falhar criticamente, os seguintes são pulados para economizar dinheiro):

```
┌────────────────────────────────────────────────────────────────┐
│ 1. PREFILTER (regex, sem IA, grátis)                           │
│    src/classify/prefilter.py                                   │
│    → descarta por título: polo, sunga, kids, tamanho fora      │
├────────────────────────────────────────────────────────────────┤
│ 2. BRAND CHECK (gpt-4o-mini + double-check 4o em conflitos)    │
│    src/classify/brand.py · prompt: verifica_sundek.py          │
│    → confirma marca Sundek + é short de banho                  │
├────────────────────────────────────────────────────────────────┤
│ 3. TIPO (gpt-4o-mini)                                          │
│    src/classify/tipo.py · prompt: liso_vs_estampado.py         │
│    → liso / estampado / logo_grande / desbotado                │
│    → flags: bicolor, tecido_brilhoso, listra lateral, etc.     │
├────────────────────────────────────────────────────────────────┤
│ Se NÃO for liso → para aqui (descartado).                      │
├────────────────────────────────────────────────────────────────┤
│ 4. COR TIER (gpt-4o-mini)                                      │
│    src/classify/cor.py · prompt: cor_tier.py                   │
│    → tier maravilhoso/muito_boa/boa/ok/ruim                    │
├────────────────────────────────────────────────────────────────┤
│ Se cor.tier == ruim → para aqui (descartado, economiza ~$0.08).│
├────────────────────────────────────────────────────────────────┤
│ 5. LISTRA SUNDEK (gpt-4o)                                      │
│    src/classify/listra.py · prompt: listra_sundek.py           │
│    → confirma listra real (≠ piping), captura cores            │
│    → combina com cor → tier_final (avaliar_combo)              │
├────────────────────────────────────────────────────────────────┤
│ Se não tem listra Sundek → para aqui (descartado).             │
├────────────────────────────────────────────────────────────────┤
│ 6. ELÁSTICO (gpt-4o)                                           │
│    src/classify/elastico.py · prompt: elastico.py              │
│    → elástico / botão / velcro                                 │
├────────────────────────────────────────────────────────────────┤
│ Se botão/velcro → para aqui (descartado).                      │
├────────────────────────────────────────────────────────────────┤
│ 7. BOLSO TRASEIRO (gpt-4o)                                     │
│    src/classify/bolso.py · prompt: bolso_traseiro.py           │
│    → tem bolso? tem nome SUNDEK? tem bolso frontal?            │
├────────────────────────────────────────────────────────────────┤
│ 8. ETIQUETA (gpt-4o-mini)                                      │
│    src/classify/etiqueta.py · prompt: etiqueta.py              │
│    → etiqueta de cintura presente? (só bônus)                  │
├────────────────────────────────────────────────────────────────┤
│ 9. SCORE (sem IA, src/classify/score.py)                       │
│    → calcula 0-100, decide comprável/médio/descartado          │
├────────────────────────────────────────────────────────────────┤
│ 10. DOUBLE-CHECK (gpt-4o) — só em ambíguos                     │
│    src/classify/reclassify_ambiguos.py                         │
│    → revalida lisos sem listra + lisos compráveis              │
└────────────────────────────────────────────────────────────────┘
```

Checkpoint: o `run.py` salva `coleta-classificada.json` a cada 20 itens. Se você re-rodar, ele **pula** itens já classificados cujas fotos não mudaram.

**Custos típicos (por item completo, com tudo):** ~$0.04 em mini + $0.04 em gpt-4o ≈ **$0.08/item**. 600 itens = ~$50 (mas com short-circuits reais cai pra ~$15–25).

---

## 5. Comandos disponíveis

Todos os comandos rodam da raiz `didi/`. Os módulos Python usam `python -m src.<modulo>`.

### 5.1 Scrape (coletar do Vinted)

**Sundek:**
```bash
python -m src.scrape.sundek                 # com browser visível (debug)
HEADLESS=true python -m src.scrape.sundek   # silencioso (produção)
```

**Vilebrequin:**
```bash
python -m src.scrape.ville
```

Salva em `data/coleta.json` (Sundek) ou `data/coleta-ville.json` (Vilebrequin). Pega até 200 itens por rodada (`MAX_ITEMS_POR_RODADA` em `config.py`).

> Quando usar: você quer **novos anúncios**. O scrape é incremental — re-coletar não duplica os mesmos IDs.

---

### 5.2 Classificar (reclassificar tudo do `coleta.json`)

```bash
python -m src.classify.run                  # 8 workers (padrão)
python -m src.classify.run --workers 4      # ajustar paralelismo
```

**Para Vilebrequin:**
```bash
python -m src.classify.ville_run
```

> Quando usar: depois de um scrape novo, ou quando você muda um prompt e quer reprocessar **tudo**.
> O cache evita gasto: itens já classificados com **mesmas fotos** são pulados.
> Se quiser ignorar o cache (reprocessar tudo do zero), apague ou renomeie `data/coleta-classificada.json` antes.

---

### 5.3 Reclassificar só uma etapa (mais barato)

Estes scripts pegam o `coleta-classificada.json` existente e refazem **uma etapa específica**, sem re-scrapear:

```bash
# Refaz só a listra (e atualiza tier_final + combo) nos lisos
python -m src.classify.reclassify_listras

# Double-check com gpt-4o nos lisos estruturalmente ambíguos
python -m src.classify.reclassify_ambiguos
```

> Quando usar: você melhorou o prompt de **uma** etapa (cor, listra, elástico, etc.) e quer ver o efeito sem pagar pelo pipeline inteiro de novo.
> **Não existe um `reclassify_cor.py` pronto** — se precisar refazer só a cor em itens já marcados como ruim, é o script ad-hoc que rodei nessa sessão (posso transformar em utilitário permanente se quiser).

---

### 5.4 Gerar relatórios HTML

```bash
python -m src.build.viewer        # data/visualizar.html — grade visual
python -m src.build.analise       # data/analise.html — auditoria por motivo
python -m src.build.diagnostico   # data/diagnostico.html — diagnóstico do funil
python -m src.build.funnel        # data/funil.html — visão do funil
python -m src.build.elastico      # data/elastico.html — só análise de elástico
```

> Quando usar: depois de qualquer reclassificação, pra ver o impacto.

---

### 5.5 UI de votação (Next.js)

```bash
cd votacao
npm install        # primeira vez
npm run dev        # http://localhost:3000
```

A UI lê `votacao/public/items.json`. Se você quer que ela reflita uma reclassificação nova, esse arquivo precisa ser regenerado (hoje é manual/script ad-hoc — o build script oficial está pendente).

---

### 5.6 Comandos auxiliares

```bash
# Inspecionar custo da última rodada
cat data/custo_por_etapa.json

# Resetar tudo (cuidado!)
rm data/coleta.json data/coleta-classificada.json
```

---

## 6. Fluxos típicos

### A. "Coletei novos itens, quero ver os compráveis"
```bash
python -m src.scrape.sundek
python -m src.classify.run
python -m src.build.analise
# abre data/analise.html
```

### B. "Mexi no prompt de cor, quero ver o impacto"
- Mudou só o prompt → reclassificação completa (mas o cache só refaz se as fotos mudaram, então o efeito do prompt **não** propaga automaticamente):
  ```bash
  rm data/coleta-classificada.json       # apaga checkpoint
  python -m src.classify.run             # roda tudo de novo
  python -m src.build.analise
  ```
- Ou mais barato: refazer só a etapa de cor em um subconjunto (script ad-hoc — peça que eu monte um `reclassify_cor.py` se virar rotina).

### C. "Só quero re-rodar a listra"
```bash
python -m src.classify.reclassify_listras
python -m src.build.analise
```

### D. "Quero ver o que o pipeline excluiu e por quê"
```bash
python -m src.build.analise
# abre data/analise.html — agrupa por motivo de exclusão
```

---

## 7. Onde mexer quando algo dá errado

| Sintoma | Onde olhar |
|---|---|
| Cor sendo classificada errada | `src/prompts/cor_tier.py` |
| Listra/piping confundindo | `src/prompts/listra_sundek.py` + `src/classify/listra.py` |
| Liso/estampado errado | `src/prompts/liso_vs_estampado.py` |
| Combinação cor+listra ruim | `src/utils/listra_tier.py` (regras hardcoded, não-IA) |
| Score injusto | `src/classify/score.py` (pontos e tetos) |
| Filtros de tamanho/preço | `src/config.py` |
| Custos explodindo | `data/custo_por_etapa.json` + checar se algum prompt está usando `detail="auto"` em vez de `"low"` |
