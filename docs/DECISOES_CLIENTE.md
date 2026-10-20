# Decisões do cliente — Sundek

Registro das regras de compra decididas pelo cliente. As pendentes estão na página
https://votacao-two.vercel.app/decisoes (votos no Redis, chaves `reaction:decisao:<id>`).

| Data | Decisão | Onde está no código | Status |
|---|---|---|---|
| out/2026 | Sem elástico: só preto e branco (marinho saiu) | `classify/score.py` (`CORES_SEM_ELASTICO`) | aplicado — confirmado pelo cliente em 20/10/2026 |
| out/2026 | Patch fluo (amarelo/lima/rosa) tem o nome SUNDEK tom sobre tom | `classify/bolso.py`, `prompts/bolso_traseiro.py` | aplicado (confirmar em /decisoes) |
| out/2026 | Lote (várias peças num anúncio): descartar | `classify/prefilter.py` (`EXCLUSAO_LOTE`), `score.py` | aplicado (confirmar em /decisoes) |
| 20/10/2026 | Faixa de UMA cor só na costura lateral (ou viés na barra da perna) **não conta** como listra Sundek | `config.LISTRA_FAIXA_UNICA="nao_conta"`; 2ª olhada em `classify/listra.py` + `prompts/listra_confirma.py`, acionada no recálculo final do `run.py` só em quem iria passar com listra de ≤1 cor | aplicado. Arco de 1 cor nas COSTAS continua contando (fora da decisão; ex.: 10351903302, 9872352434, 9472320096) |
| 20/10/2026 | Short de moletom (não é de banho): descartar sempre | `classify/prefilter.py` (palavras de agasalho no título) + `prompts/verifica_sundek.py` (visão) | aplicado |
| 20/10/2026 | Sundek Goldenwave (linha premium): **não interessa** — descartar | `classify/prefilter.py` (`EXCLUSAO_GOLDENWAVE`), `prompts/verifica_sundek.py`, `classify/brand.py` | aplicado |
