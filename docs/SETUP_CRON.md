# ⏰ Setup do cron de produção

Workflow: `.github/workflows/scrape-cron.yml`

## Horários (3x/dia)

| Horário Brasil (BRT) | UTC | Cron |
|---|---|---|
| 05:00 | 08:00 | `0 8 * * *` |
| 13:00 | 16:00 | `0 16 * * *` |
| 19:30 | 22:30 | `30 22 * * *` |

## O que faz cada execução

1. **Scrape Sundek** (`python -m src.scrape.sundek`)
2. **Classifica Sundek** com cache (só itens novos)
3. **Gera `data/analise.html`**
4. **Deploy no Vercel** (`votacao/public/analise.html`)
5. **Commita JSONs** atualizados de volta no repo (preserva histórico)
6. **Em seguida**, mesma coisa pro Vilebrequin

⚠️ Sundek e Ville rodam em jobs separados pra não competir cota OpenAI simultaneamente.

---

## ✅ Setup obrigatório (1x, fazer agora)

### 1. Secrets no GitHub
Ir em **github.com/danielreinaux/didi → Settings → Secrets and variables → Actions → New repository secret**

Criar **dois secrets**:

| Nome do secret | Valor |
|---|---|
| `OPENAI_API_KEY` | a chave OpenAI (sk-proj-...) |
| `VERCEL_TOKEN` | token Vercel (gerar em https://vercel.com/account/tokens) |

### 2. Permissões do bot do Actions
Em **Settings → Actions → General → Workflow permissions**:
- Marcar **"Read and write permissions"** (pro bot conseguir commitar de volta os JSONs)
- Marcar **"Allow GitHub Actions to create and approve pull requests"**

### 3. Testar primeiro
Antes do cron rodar sozinho, dispare manual pra ver se funciona:
- Vai em **Actions → Scrape + Classify (3x/dia) → Run workflow → Run workflow**
- Acompanha em tempo real
- Custo de teste: ~$3 USD (1 rodada Sundek + Ville)

---

## 📂 O que fica salvo no repo a cada rodada

Cada execução commita:
- `data/coleta.json` (último scrape Sundek)
- `data/coleta-classificada.json`
- `data/coleta-ville.json`
- `data/coleta-ville-classificada.json`
- `data/historico.json` (preço por ID ao longo do tempo)
- `data/custo_por_etapa.json`
- `data/analise.html`
- `votacao/public/analise.html`

Repositório cresce, mas é OK até ~6 meses (depois migra pra Supabase).

---

## 💰 Custo previsto

| Item | Mensal |
|---|---|
| GitHub Actions | R$ 0 (free tier 2000 min/mês — vamos usar ~300min) |
| Vercel hobby | R$ 0 |
| OpenAI (3 runs × 30 dias) | **~R$ 200-385** (depende de cache hit) |

---

## 🔧 Troubleshooting

### Job falha com "Rate limit"
- OpenAI Tier 1 só suporta 30K TPM (gpt-4o). Reduzir `--workers` pra 1 e aumentar `INTERVALO_GPT4O` no `ratelimit.py`.

### Push falha com "Updates were rejected"
- Outro job commitou no meio. O `git pull --rebase` antes do push deve resolver.

### Vercel deploy falha
- Verificar se `VERCEL_TOKEN` ainda válido (eles expiram).
- Verificar se `votacao/` ainda está linkado: rodar `cd votacao && npx vercel link`.

### Quer parar o cron temporariamente
- Em **Actions → Scrape + Classify (3x/dia) → ··· → Disable workflow**

---

## 📅 Próximos passos depois

- [ ] Migrar persistência pra Supabase (ver `ROADMAP.md` Frente 3)
- [ ] Notificação Telegram quando aparecer comprável novo
- [ ] Reduzir frequência se cache hit > 90% (1x/dia já basta)
