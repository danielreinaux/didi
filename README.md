# Didi — Radar Sundek/Vilebrequin

Sistema autônomo de scraping + classificação por IA para shorts Sundek e Vilebrequin.

## Estrutura

```
src/
  config.py             filtros de busca (do manual)
  browser.py            setup do Playwright (entrada no site, cookies)
  extract.py            extração de dados de uma página de item
  prefilter.py          filtro de título (regex, sem IA)
  classify.py           classificação liso/estampado/logo_grande (vision)
  classify_color.py     classificação de cor em 4 tiers (vision, só lisos)
  classify_brand.py     verifica marca Sundek + formato short (vision)
  prompts/              prompts dos 3 classificadores
  sources/
    vinted.py           scraper do Vinted (ES)
  scrape.py             entry point — coleta
  classify_run.py       entry point — classifica coleta.json
  build_viewer.py       gera HTML pra inspeção
data/
  coleta.json
  coleta-classificada.json
  screenshots/
docs/
  proposta.md, Regras_Compra_Shorts-4.docx
demos/
  index.html, index2.html (mockups visuais pro cliente)
```

## Setup (primeira vez)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
echo "OPENAI_API_KEY=sk-..." > .env
```

## Comandos

```bash
.venv/bin/python -m src.scrape           # com browser visível (debug)
HEADLESS=true .venv/bin/python -m src.scrape   # silencioso (produção)
.venv/bin/python -m src.classify_run     # classifica coleta.json
.venv/bin/python -m src.build_viewer     # gera data/visualizar.html
```

## Pipeline de classificação

Cada item passa por:

1. **Prefilter** (regex no título, sem IA) → descarta polo, t-shirt, sunga, slip…
2. **Verifica marca + formato** (vision) → descarta não-Sundek e sungas que escaparam
3. **Liso / estampado / logo_grande** (vision)
4. **Tier de cor** (vision, só nos lisos) → muito_boa / boa / ok / ruim
