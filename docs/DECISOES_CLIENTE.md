# Decisões do cliente — Sundek

Registro das regras de compra decididas pelo cliente. As pendentes estão na página
https://votacao-two.vercel.app/decisoes (votos no Redis, chaves `reaction:decisao:<id>`).

| Data | Decisão | Onde está no código | Status |
|---|---|---|---|
| out/2026 | Sem elástico: só preto e branco (marinho saiu) | `classify/score.py` (`CORES_SEM_ELASTICO`) | aplicado — confirmado pelo cliente em 20/10/2026 |
| out/2026 | Patch fluo (amarelo/lima/rosa) tem o nome SUNDEK tom sobre tom | `classify/bolso.py`, `prompts/bolso_traseiro.py` | aplicado — confirmado em /decisoes |
| 21/10/2026 | Lote (várias peças num anúncio): **mostrar como barganha** (antes: descartar) | `classify/score.py` (lote → medio); `prefilter.py` não descarta mais | aplicado |
| 20/10/2026 | Faixa de UMA cor só na costura lateral (ou viés na barra da perna) **não conta** como listra Sundek | `config.LISTRA_FAIXA_UNICA="nao_conta"`; 2ª olhada em `classify/listra.py` + `prompts/listra_confirma.py`, acionada no recálculo final do `run.py` só em quem iria passar com listra de ≤1 cor | aplicado. Arco de 1 cor nas COSTAS continua contando (fora da decisão; ex.: 10351903302, 9872352434, 9472320096) |
| 20/10/2026 | Short de moletom (não é de banho): descartar sempre | `classify/prefilter.py` (palavras de agasalho no título) + `prompts/verifica_sundek.py` (visão) | aplicado |
| 20/10/2026 | Sundek Goldenwave (linha premium): **não interessa** — descartar | `classify/prefilter.py` (`EXCLUSAO_GOLDENWAVE`), `prompts/verifica_sundek.py`, `classify/brand.py` | aplicado |
| 21/10/2026 | Elástico + anúncio até €10: o preço perdoa bolso só logo, sem listra/faixa única, brilhoso e bicolor (vira comprável). Cor ruim e os motivos graves continuam descartando | `classify/score.py` (`PRECO_BARATO_ELASTICO`, `PERDOA_BARATO_ELASTICO`); `run.py` não pula o elástico em sem-listra até €10 | aplicado |
| 21/10/2026 | Verde-limão com listra azul/branca vale (ruim → ok) | `utils/listra_tier.py` (`limao_salvavel`); `run.py` roda a listra no verde-limão | aplicado |
| 21/10/2026 | Roxo/violeta = cor ruim | `classify/cor.py` (`_normalizar_tier`) | aplicado |
| 21/10/2026 | Laranja salmão pode ser bem classificada (ok/ruim → boa) | `classify/cor.py` (`_normalizar_tier`) | aplicado |
| 21/10/2026 | Rosa choque: só com preço muito bom | já é assim: tier "ok" pontua pouco e só passa com preço baixo | sem mudança |
| 21/10/2026 | Listra dourada/bege geralmente ruim; prata ok | `utils/listra_tier.py`: listra dominada por dourado/bege (sem cores vivas) rebaixa a cor para no máximo "ok" | aplicado (rebaixa, não exclui — o mini chama de "bege" a faixa creme) |
| 21/10/2026 | Patch claro tom sobre tom = coleção antiga (descartar) | comportamento atual (bolso só logo) | sem mudança |
| 21/10/2026 | Marrom acetinado = ruim | rótulo do gabarito mantido | sem mudança |
| 21/10/2026 | Desbotado "de borda" (só marquinhas num close) não é desbotado | 2ª olhada com Claude Haiku via OpenRouter (patch pronto) | pendente: precisa do secret OPENROUTER_API_KEY no GitHub |
| 21/10/2026 | Cor: a diferença entre itens da mesma cor do corpo vem das LISTRAS (navy, grafite, royal) — o tier do gabarito é a combinação corpo + listras | `utils/listra_tier.py` (calibração em andamento) | em andamento |
| 21/10/2026 | Etiqueta M520 = modelo com botão? "Não sei" | — | descartado |
| 21/10/2026 | Correções do gabarito: 11 fechamentos → cordão; cs01 tem nome; 9281059882 tem listra; 9267294121/9283498191/9280097121 são Sundek; 9289304070 tem velcro; 9285757049 cor ruim | Redis `gabarito:*` via /api/gabarito | pendente de gravação |
