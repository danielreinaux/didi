# 🗺️ Roadmap Didi — Maio 2026

Documento vivo. Atualizar conforme avançamos.

---

## 🐢 Frente 1 — Pipeline Vilebrequin (próximos passos)

Status hoje: scrape OK (900 itens), classificação parcial, **0 itens com decisão final**.

### 1.1 Refazer prompt `tartaruga.py`
- [ ] Adicionar categoria **`padrao_vilebrequin_classico`** (peixes, corais, estrelas do mar, fogos, âncoras, frutas, plantas)
- [ ] Adicionar categoria **`padrao_generico`** (estampa sem identidade Vilebrequin)
- [ ] Corrigir bug `detail="auto"` → `"low"` (mesmo bug que tinha no brand do Sundek, gasta 10x mais)
- [ ] Refinar saída JSON com `cor_principal`, `tartaruga_variedade`, `padrao_identificado`

### 1.2 Integrar autenticidade dedicada
- [x] Criado `src/prompts/autenticidade_ville.py` (critério único do manual: padrão continua no bolso)
- [x] Criado `src/classify/autenticidade_ville.py` com zoom no bolso (high) + fotos gerais (low)
- [ ] Integrar no `src/classify/ville_run.py`: rodar após o brand check confirmar `e_vilebrequin=sim`
- [ ] Remover a verificação de autenticidade duplicada de `verifica_ville.py` (foca só em marca)

### 1.3 Re-classificar 566 itens
- [ ] Rodar prompt novo de tartaruga em 566 itens (124 lisos + 36 peq + 14 grande + 392 outro)
- [ ] Custo estimado: **~$1.40** (mini com detail=low)
- [ ] Rodar autenticidade dedicada nos itens marcados como Vilebrequin
- [ ] Custo estimado: **~$15** (gpt-4o com zoom high)

### 1.4 Criar `src/classify/score_ville.py`
Regras conforme manual:
- [ ] Tartaruga grande = **comprável quase 100%** (87% do histórico)
- [ ] Padrão clássico (peixes/corais/etc.) = **médio** (avaliar cor + tamanho + preço)
- [ ] Liso + cor neutra (preto/branco/navy/cinza) + ≤€42 = **comprável**
- [ ] Falso = **descartado**
- [ ] Tamanho M = prioridade máxima; L = bom; S/XL = aceitáveis
- [ ] Faixas de preço: €40-70 ideal; €70-80 condicional; >€80 barganha
- [ ] Cor: azul + azul escuro dominam (43% histórico); laranja/vermelho aceitos com tartaruga grande

### 1.5 Criar `src/build/analise_ville.py`
- [ ] Espelho do `analise.py` do Sundek
- [ ] Tags específicas: autenticidade (original/falso), padrão tartaruga (grande/pequena/clássico/liso)
- [ ] Drill-down por motivo de exclusão
- [ ] Botão "discordo" + textarea (mesmo padrão Sundek, namespace `analise_ville:`)

---

## 🧹 Frente 2 — Refatorações e limpezas (Sundek)

### 2.1 Limpar arquivos órfãos
- [ ] Apagar `src/scrape/async_.py` (não funcionou com Playwright sync, dead code)
- [ ] Apagar `src/classify/ocr_patch.py` (OCR descartado — Vinted só serve fotos 800x800)
- [ ] Renomear `nao_vilebrequin` → `nao_ville` (4 itens com tipo inconsistente)

### 2.2 Limpar prompts órfãos
- [ ] Remover campos `bicolor` e `tem_bolso_frontal` do `liso_vs_estampado.py` (já migrados pra prompts dedicados)
- [ ] Confirmar que `classify/tipo.py` não está duplicando trabalho do `bolso.py`/`listra.py`

### 2.3 Fallback do bolso
- [ ] `classify/bolso.py` — quando `crop_bolso` falha, hoje manda 6 fotos em high. Mudar fallback pra low (economia ~70% no caso)

### 2.4 Reclassify pós-reorg
- [ ] Testar `src/classify/reclassify_ambiguos.py` e `src/classify/reclassify_listras.py` no novo paths
- [ ] Garantir que `_track` do cost_tracker está sendo chamado corretamente em todas as etapas

---

## 🗄️ Frente 3 — Banco de dados (SAIR DO JSON)

**Hoje:** tudo em JSON em disco (`data/*.json`).
- ✅ Simples, versionável em git
- ❌ Não escala — 2000+ itens ficam lentos
- ❌ Cron na nuvem precisa "voltar" os dados pro repo
- ❌ Viewer público lê arquivo estático (não atualiza em tempo real)
- ❌ Sem queries (filtrar "compráveis Sundek azuis €10-15" exige iterar tudo)

### 3.1 Escolha do DB

| Opção | Free tier | Vercel-friendly | Notas |
|---|---|---|---|
| **Supabase** (Postgres) ⭐ | 500MB + auth + storage | ✅ excelente | API REST pronta, dashboard incluso |
| **Neon** (Postgres) | 3GB serverless | ✅ parceiro oficial Vercel | Postgres puro, mais barato em escala |
| Turso (SQLite distribuído) | 9GB | OK | Simples, edge-first |
| MongoDB Atlas | 512MB | OK | NoSQL — temos pouco motivo |
| Vercel KV (Redis) | 30K req/dia | ✅ nativo | Bom só pra cache/sessão, não pra dados principais |

**Sugestão: Supabase** — vem com API REST + dashboard + auth (útil pra futuro login do stakeholder).

### 3.2 Schema mínimo (Postgres)

```sql
-- Itens (Sundek e Vilebrequin juntos)
CREATE TABLE items (
  id BIGINT PRIMARY KEY,            -- id do Vinted
  marca TEXT NOT NULL,              -- 'sundek' | 'vilebrequin'
  url TEXT NOT NULL,
  titulo TEXT,
  preco_num NUMERIC,                -- ex: 12.50
  preco_str TEXT,                   -- '12,50 €'
  tamanho TEXT,
  estado TEXT,
  cor_extracted TEXT,               -- cor que o Vinted reporta
  vendedor JSONB,
  fotos TEXT[],                     -- array de URLs
  scraped_em TIMESTAMPTZ NOT NULL,
  ativo BOOLEAN DEFAULT true,       -- false quando sumir do scrape (= vendido)
  vendido_em TIMESTAMPTZ
);
CREATE INDEX idx_items_marca ON items(marca);
CREATE INDEX idx_items_ativo ON items(ativo);

-- Classificação (1 linha por item)
CREATE TABLE classificacoes (
  item_id BIGINT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  tipo TEXT,                        -- 'liso' | 'estampado' | 'nao_short' | etc.
  cor_principal TEXT,
  tier TEXT,                        -- 'maravilhoso' | 'muito_boa' | 'boa' | 'ok' | 'ruim'
  listra_cores TEXT[],
  bolso_tem_nome BOOLEAN,
  tem_elastico BOOLEAN,
  tipo_fechamento TEXT,             -- 'elastico' | 'cordao' | 'botao' | 'velcro'
  tem_etiqueta BOOLEAN,
  -- Vilebrequin específico
  autenticidade TEXT,
  padrao_ville TEXT,                -- 'tartaruga_grande' | 'classico' | etc.
  -- raw JSON de evidências
  evidencias JSONB,
  fotos_classificadas_em TIMESTAMPTZ DEFAULT now()
);

-- Score + decisão
CREATE TABLE scores (
  item_id BIGINT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  score INT,
  teto NUMERIC,
  decisao TEXT,                     -- 'compravel' | 'medio' | 'descartado'
  motivo_exclusao TEXT,
  motivo TEXT,
  breakdown JSONB,
  calculado_em TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_scores_decisao ON scores(decisao);

-- Histórico de preços
CREATE TABLE precos_historico (
  id BIGSERIAL PRIMARY KEY,
  item_id BIGINT REFERENCES items(id) ON DELETE CASCADE,
  data TIMESTAMPTZ NOT NULL,
  preco_str TEXT,
  preco_num NUMERIC
);
CREATE INDEX idx_precos_item ON precos_historico(item_id, data);

-- Feedback humano (reações + comentários do stakeholder)
CREATE TABLE feedback (
  id BIGSERIAL PRIMARY KEY,
  item_id BIGINT REFERENCES items(id),
  namespace TEXT,                   -- 'viewer' | 'analise' | etc.
  reacao TEXT,                      -- 'gostei' | 'medio' | 'nao' | 'discordo'
  comentario TEXT,
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- Custo por etapa (acompanhamento)
CREATE TABLE custos (
  id BIGSERIAL PRIMARY KEY,
  data DATE NOT NULL,
  etapa TEXT,                       -- 'brand' | 'bolso' | 'listra' | etc.
  modelo TEXT,                      -- 'gpt-4o-mini' | 'gpt-4o'
  chamadas INT,
  tokens_in BIGINT,
  tokens_out BIGINT,
  custo_usd NUMERIC
);
```

### 3.3 Migração faseada
- [ ] **Fase 1**: criar projeto Supabase + schema (1h)
- [ ] **Fase 2**: módulo `src/utils/db.py` (CRUD básico via supabase-py)
- [ ] **Fase 3**: adaptar `scrape/*` pra escrever no DB em paralelo ao JSON (período de transição)
- [ ] **Fase 4**: adaptar `classify/run.py` pra ler/escrever DB
- [ ] **Fase 5**: adaptar `build/*.py` pra ler DB → ainda gerar HTML estático (já temos o pipeline pronto)
- [ ] **Fase 6**: cortar a dependência do JSON (mover pra histórico/backup)

### 3.4 Custo
- Supabase free tier: **R$ 0** até 500MB (suficiente pra ~50K itens)
- Acima disso: ~$25/mês (dificilmente vai precisar)

---

## ☁️ Frente 4 — Automação (cron na nuvem)

### 4.1 Escolha: **GitHub Actions** ⭐
- **Grátis** (2000 min/mês no free tier — sobra muito)
- Cron nativo
- Roda Playwright sem problema
- Já temos repo no GitHub

### 4.2 Workflow
- [ ] Criar `.github/workflows/scrape-daily.yml`
- [ ] Schedule: `0 8,14,20 * * *` (3x/dia em UTC)
- [ ] Secrets: `OPENAI_API_KEY`, `VERCEL_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`
- [ ] Steps:
  1. Setup Python 3.12 + Playwright
  2. Rodar `python -m src.scrape.sundek`
  3. Rodar `python -m src.classify.run`
  4. Rodar `python -m src.scrape.ville` (separado, pra não competir cota)
  5. Rodar `python -m src.classify.ville_run`
  6. Gerar HTMLs (`build.analise` + `build.analise_ville`)
  7. Deploy `votacao/public/*.html` no Vercel
  8. (se ainda usando JSON) commitar `data/` no repo
  9. (se já migrou pra DB) escrever direto no Supabase

### 4.3 Limites a se preocupar
- GitHub Actions: 6h por job (sobra muito, cada rodada deve ser ~30min)
- OpenAI: TPM (já temos `ratelimit.py` cuidando)
- Vinted: pode bloquear se rodar demais; 3x/dia é seguro

### 4.4 Notificação (próxima fase)
- [ ] Webhook Telegram quando aparecer comprável novo
- [ ] Email semanal com resumo (custos + compráveis + barganhas)

---

## 💰 Custo total mensal projetado (REALISTA, ago/2026)

Premissas reais informadas pelo cliente:
- **Sundek**: ~2.000 anúncios novos/mês
- **Vilebrequin**: ~300 anúncios novos/mês

| Item | Mensal |
|---|---|
| GitHub Actions (cron) | R$ 0 |
| Supabase (DB) | R$ 0 (free tier) |
| Vercel (viewer + analise) | R$ 0 (hobby) |
| **OpenAI Sundek** (2.000 × $0.024) | **~R$ 240** |
| **OpenAI Vilebrequin** (300 × $0.08) | **~R$ 120** |
| OpenAI double-check (~5%) | ~R$ 25 |
| **TOTAL hoje (sem otimização)** | **~R$ 385/mês** |
| Com Batch API (-50%) | **~R$ 200/mês** |
| Stack completo (Batch + cache agressivo + tartaruga otimizada) | **~R$ 100-150/mês** |

ROI: cada Sundek bem revendido = R$ 200-400 de margem. Vilebrequin = R$ 500-1000.
**1 venda boa/mês paga 4-6 meses de pipeline**.

---

## 📅 Ordem sugerida

1. **Pipeline Vilebrequin** (1.1 → 1.5) — desbloqueia Ville
2. **Refatorações leves** (Frente 2) — limpa débitos
3. **Banco de dados** (Frente 3) — fundação pra escalar
4. **Cron + automação** (Frente 4) — fecha o ciclo

---

*Última atualização: 26/05/2026*
