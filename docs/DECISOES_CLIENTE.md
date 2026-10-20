# Decisões do cliente — Sundek

Registro das regras de compra decididas pelo cliente. As pendentes estão na página
https://votacao-two.vercel.app/decisoes (votos no Redis, chaves `reaction:decisao:<id>`).

| Data | Decisão | Onde está no código | Status |
|---|---|---|---|
| out/2026 | Sem elástico: só preto e branco (marinho saiu) | `classify/score.py` (`CORES_SEM_ELASTICO`) | aplicado |
| out/2026 | Patch fluo (amarelo/lima/rosa) tem o nome SUNDEK tom sobre tom | `classify/bolso.py`, `prompts/bolso_traseiro.py` | aplicado (confirmar em /decisoes) |
| out/2026 | Lote (várias peças num anúncio): descartar | `classify/prefilter.py` (`EXCLUSAO_LOTE`), `score.py` | aplicado (confirmar em /decisoes) |
| 20/10/2026 | Faixa de UMA cor só na costura lateral **não conta** como listra Sundek | — | decidido; falta implementar: o modo estrito do prompt (`config.LISTRA_FAIXA_UNICA="nao_conta"`) descarta listras reais de 2+ cores no mini (gabarito: listra 93%→80%) — precisa de uma 2ª olhada focada antes de ligar |
| 20/10/2026 | Short de moletom (não é de banho): descartar sempre | `classify/prefilter.py` (palavras de agasalho no título) + `prompts/verifica_sundek.py` (visão) | aplicado |
| 20/10/2026 | Sundek Goldenwave (linha premium): **não interessa** — descartar | `classify/prefilter.py` (`EXCLUSAO_GOLDENWAVE`), `prompts/verifica_sundek.py`, `classify/brand.py` | aplicado |
