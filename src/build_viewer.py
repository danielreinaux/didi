"""Lê data/coleta-classificada.json e gera data/visualizar.html."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _aba(it: dict) -> str:
    if it.get("manual_exclusao"):
        return "skip"
    sc = it.get("score") or {}
    if sc.get("motivo_exclusao"):
        return "nao_selecao"
    decisao = sc.get("decisao", "")
    if decisao == "compravel":
        return "compravel"
    if decisao == "medio":
        return "ok"
    return "nao_compravel"


def card_html(it: dict) -> str:
    c = it.get("classificacao") or {}
    tipo = c.get("tipo") or "sem"
    cor_raw = it.get("cor")
    if isinstance(cor_raw, dict):
        cor = cor_raw
        cor_str = cor_raw.get("cor_principal") or ""
    else:
        cor = None
        cor_str = cor_raw or ""

    fotos_arr = (it.get("fotos") or [])[:8]
    foto = fotos_arr[0] if fotos_arr else ""
    fotos_outras = "".join(f'<img src="{u}" loading="lazy">' for u in fotos_arr[1:])

    # Score
    sc = it.get("score") or {}
    score_val = sc.get("score", 0)
    teto = sc.get("teto")
    motivo_exclusao = sc.get("motivo_exclusao", "")
    aba = _aba(it)

    if aba == "compravel":
        score_html = f'<div class="score compravel">✓ Comprável · <b>{score_val}pts</b></div>'
    elif aba == "ok":
        score_html = f'<div class="score ok">~ Ok · <b>{score_val}pts</b> · teto €{teto}</div>'
    elif aba == "nao_compravel":
        score_html = f'<div class="score nao">✗ <b>{score_val}pts</b> · {escape(sc.get("motivo",""))}</div>'
    else:
        score_html = ""

    # Características em linha
    tags = []
    if isinstance(cor_raw, dict) and cor_raw.get("tier"):
        tier = cor_raw.get("tier_final") or cor_raw["tier"]
        nome_cor = escape(cor_raw.get("cor_principal") or "")
        tags.append(f'<span class="tag tag-cor tag-{tier}">{nome_cor}</span>')

    listras = cor_raw.get("cores_listras") if isinstance(cor_raw, dict) else []
    if listras:
        listra_tier = cor_raw.get("listra_tier", "") if isinstance(cor_raw, dict) else ""
        arrow = " ↑" if listra_tier == "salva" else (" ↓" if listra_tier == "penaliza" else "")
        tags.append(f'<span class="tag tag-listra">listras{arrow}</span>')

    el = it.get("elastico") or {}
    if el.get("tem_elastico") is True:
        tags.append('<span class="tag tag-green">elástico</span>')
    elif el.get("tem_elastico") is False:
        tags.append('<span class="tag tag-warn">sem elástico</span>')

    etq = it.get("etiqueta") or {}
    if etq.get("tem_etiqueta") is True:
        tags.append('<span class="tag tag-blue">etiqueta</span>')

    tags_html = "".join(tags)

    item_id = escape(str(it.get("id") or ""))
    url = escape(it.get("url") or "")
    titulo = escape(it.get("titulo") or "(sem título)")
    preco = escape(it.get("preco_total") or it.get("preco") or "")
    tamanho = escape(it.get("tamanho") or "?")

    return f"""<article class="card" data-id="{item_id}" data-aba="{aba}">
  <a href="{url}" target="_blank" class="thumb-wrap">
    <img class="thumb" src="{foto}" loading="lazy">
    <span class="tipo-pill {tipo}">{tipo}</span>
  </a>
  <div class="body">
    <div class="title"><a href="{url}" target="_blank">{titulo}</a></div>
    <div class="meta">{preco} · {tamanho} · {escape(cor_str or "?")}</div>
    {score_html}
    <div class="tags">{tags_html}</div>
    <div class="reactions" data-id="{item_id}">
      <button class="react-btn" data-id="{item_id}" data-val="gostei">👍 Gostei</button>
      <button class="react-btn" data-id="{item_id}" data-val="medio">😐 Médio</button>
      <button class="react-btn" data-id="{item_id}" data-val="nao">👎 Não</button>
    </div>
    <textarea class="observacao" data-id="{item_id}" placeholder="Observação..." rows="2"></textarea>
    <a class="open-btn" href="{url}" target="_blank">Abrir ↗</a>
    <details class="fotos">
      <summary>+ fotos ({len(fotos_arr)})</summary>
      <div class="fotos-grid">{fotos_outras}</div>
    </details>
  </div>
</article>"""


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())

    from .score import calcular_score
    for it in itens:
        if "score" not in it:
            it["score"] = calcular_score(it)

    # Filtra manuais e não-seleção, ordena por score desc
    itens = [i for i in itens if _aba(i) != "skip"]
    itens = sorted(itens, key=lambda x: -(x.get("score") or {}).get("score", 0))

    cnt = lambda a: sum(1 for i in itens if _aba(i) == a)
    n_c, n_o, n_n = cnt("compravel"), cnt("ok"), cnt("nao_compravel")

    cards = "\n".join(card_html(it) for it in itens)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Shorts</title>
<style>
:root {{
  --bg: #f2f2f0; --surface: #fff; --ink: #18181b;
  --soft: #52525b; --mute: #a1a1aa; --border: #e4e4e7; --r: 14px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--ink);
}}

/* Tabs */
.tabs {{
  position: sticky; top: 0; z-index: 30;
  background: var(--surface); border-bottom: 1px solid var(--border);
  display: flex; overflow-x: auto; -webkit-overflow-scrolling: touch;
}}
.tab {{
  flex: 1; min-width: 90px; height: 50px;
  display: flex; align-items: center; justify-content: center; gap: 5px;
  font-size: 13px; font-weight: 600; color: var(--mute);
  border: none; border-bottom: 3px solid transparent;
  background: none; cursor: pointer; padding: 0 10px; white-space: nowrap;
  transition: color .15s, border-color .15s;
}}
.tab:hover {{ color: var(--ink); }}
.tab.active {{ color: var(--ink); border-bottom-color: var(--ink); }}
.cnt {{
  padding: 1px 6px; border-radius: 99px; font-size: 11px; background: #f0f0ee;
}}
.tab[data-tab="compravel"] .cnt {{ background: #dcfce7; color: #14532d; }}
.tab[data-tab="ok"] .cnt {{ background: #fef9c3; color: #713f12; }}
.tab[data-tab="nao_compravel"] .cnt {{ background: #fee2e2; color: #7f1d1d; }}

/* Grid */
main {{ padding: 14px 10px 80px; max-width: 900px; margin: 0 auto; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
  gap: 12px;
}}
@media (max-width: 500px) {{
  .grid {{ grid-template-columns: 1fr 1fr; gap: 9px; }}
  main {{ padding: 10px 8px 80px; }}
}}

/* Card */
.card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); overflow: hidden;
  display: flex; flex-direction: column;
  transition: box-shadow .15s;
}}
.card:hover {{ box-shadow: 0 4px 18px rgba(0,0,0,.08); }}

.thumb-wrap {{
  position: relative; aspect-ratio: 1; display: block;
  overflow: hidden; background: #e8e8e6;
}}
.thumb {{ width: 100%; height: 100%; object-fit: cover; display: block; }}

.tipo-pill {{
  position: absolute; top: 7px; right: 7px;
  padding: 2px 7px; border-radius: 6px;
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  color: #fff; letter-spacing: .04em;
}}
.tipo-pill.liso {{ background: #16a34a; }}
.tipo-pill.estampado {{ background: #ef4444; }}
.tipo-pill.logo_grande {{ background: #b45309; }}
.tipo-pill.desbotado, .tipo-pill.indefinido, .tipo-pill.nao_short,
.tipo-pill.nao_sundek, .tipo-pill.sem {{ background: #71717a; }}

.body {{ padding: 10px 11px 11px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}

.title {{ font-size: 13px; font-weight: 600; line-height: 1.35; }}
.title a {{ color: var(--ink); }}
.title a:hover {{ text-decoration: underline; }}

.meta {{ font-size: 11.5px; color: var(--soft); }}

/* Score — linha única discreta */
.score {{
  font-size: 12px; font-weight: 600; padding: 4px 9px; border-radius: 7px;
}}
.score.compravel {{ background: #f0fdf4; color: #15803d; border-left: 2px solid #4ade80; }}
.score.ok {{ background: #fefce8; color: #a16207; border-left: 2px solid #fde047; }}
.score.nao {{ background: #fff1f2; color: #be123c; border-left: 2px solid #fda4af; }}

/* Tags em linha */
.tags {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.tag {{
  padding: 2px 7px; border-radius: 99px; font-size: 11px; font-weight: 600;
}}
.tag-cor.tag-maravilhoso {{ background: #ede9fe; color: #6d28d9; }}
.tag-cor.tag-muito_boa {{ background: #dcfce7; color: #15803d; }}
.tag-cor.tag-boa {{ background: #ecfccb; color: #4d7c0f; }}
.tag-cor.tag-ok {{ background: #fef9c3; color: #a16207; }}
.tag-cor.tag-ruim {{ background: #fee2e2; color: #b91c1c; }}
.tag-listra {{ background: #f0f9ff; color: #0369a1; }}
.tag-green {{ background: #dcfce7; color: #166534; }}
.tag-warn {{ background: #fef9c3; color: #713f12; }}
.tag-blue {{ background: #dbeafe; color: #1d4ed8; }}

/* Reações */
.reactions {{ display: flex; gap: 6px; }}
.react-btn {{
  flex: 1; padding: 7px 4px; border-radius: 8px; font-size: 12px; font-weight: 600;
  border: 1.5px solid var(--border); background: var(--bg); color: var(--soft);
  cursor: pointer; transition: all .15s; text-align: center;
}}
.react-btn:hover {{ border-color: #a1a1aa; color: var(--ink); }}
.react-btn.active[data-val="gostei"] {{ background: #dcfce7; border-color: #4ade80; color: #15803d; }}
.react-btn.active[data-val="medio"] {{ background: #fef9c3; border-color: #fde047; color: #a16207; }}
.react-btn.active[data-val="nao"] {{ background: #fee2e2; border-color: #fca5a5; color: #b91c1c; }}

/* Observação */
.observacao {{
  width: 100%; border: 1px solid var(--border); border-radius: 8px;
  padding: 7px 9px; font: 12.5px/1.4 -apple-system, sans-serif;
  color: var(--ink); background: #fafaf8; resize: none; outline: none;
  transition: border-color .15s, background .15s;
}}
.observacao:focus {{ border-color: #a1a1aa; background: #fff; }}
.observacao.has-text {{ border-color: #4ade80; background: #f0fdf4; }}

.open-btn {{
  display: block; text-align: center;
  font-size: 13px; font-weight: 700; color: #1d4ed8;
  padding: 8px; border-radius: 8px; background: #eff6ff;
  transition: background .15s;
}}
.open-btn:hover {{ background: #dbeafe; }}

details.fotos {{ font-size: 11.5px; color: var(--mute); cursor: pointer; }}
details.fotos summary {{ padding: 2px 0; cursor: pointer; }}
.fotos-grid {{
  display: grid; grid-template-columns: repeat(4,1fr); gap: 4px; margin-top: 6px;
}}
.fotos-grid img {{ width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 6px; }}

.hidden {{ display: none !important; }}
</style>
</head>
<body>

<div class="tabs">
  <button class="tab active" data-tab="compravel">Comprável <span class="cnt">{n_c}</span></button>
  <button class="tab" data-tab="ok">Ok <span class="cnt">{n_o}</span></button>
  <button class="tab" data-tab="nao_compravel">Não comprável <span class="cnt">{n_n}</span></button>
</div>

<main><div class="grid">{cards}</div></main>

<script>
const API_COMMENTS = 'https://votacao-two.vercel.app/api/comments';
const API_REACTIONS = 'https://votacao-two.vercel.app/api/reactions';
let activeTab = 'compravel';
let saveTimers = {{}};

async function post(url, body) {{
  try {{
    await fetch(url, {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body) }});
  }} catch(e) {{ console.warn('Erro ao salvar', e); }}
}}

// Carrega tudo de uma vez ao abrir
async function loadAll() {{
  try {{
    const [cr, rr] = await Promise.all([fetch(API_COMMENTS), fetch(API_REACTIONS)]);
    const comments = await cr.json();
    const reactions = await rr.json();

    document.querySelectorAll('.observacao').forEach(box => {{
      const text = comments[box.dataset.id];
      if (text) {{ box.value = text; box.classList.add('has-text'); }}
    }});

    document.querySelectorAll('.card').forEach(card => {{
      const id = card.dataset.id;
      const r = reactions[id];
      if (r?.reaction) {{
        card.querySelectorAll('.react-btn').forEach(btn => {{
          btn.classList.toggle('active', btn.dataset.val === r.reaction);
        }});
      }}
    }});
  }} catch(e) {{ console.warn('Erro ao carregar', e); }}
}}

function applyFilters() {{
  document.querySelectorAll('.card').forEach(c => {{
    c.classList.toggle('hidden', c.dataset.aba !== activeTab);
  }});
}}

// Tabs
document.querySelectorAll('.tab').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeTab = btn.dataset.tab;
    applyFilters();
  }});
}});

// Reações — toggle: clicar no mesmo remove
document.querySelectorAll('.react-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const id = btn.dataset.id;
    const val = btn.dataset.val;
    const card = btn.closest('.card');
    const isActive = btn.classList.contains('active');
    card.querySelectorAll('.react-btn').forEach(b => b.classList.remove('active'));
    if (!isActive) {{
      btn.classList.add('active');
      post(API_REACTIONS, {{ id, reaction: val }});
    }} else {{
      post(API_REACTIONS, {{ id, reaction: '' }});
    }}
  }});
}});

// Observação — salva 800ms após parar de digitar
document.querySelectorAll('.observacao').forEach(box => {{
  box.addEventListener('input', () => {{
    const id = box.dataset.id;
    box.classList.toggle('has-text', !!box.value.trim());
    clearTimeout(saveTimers[id]);
    saveTimers[id] = setTimeout(() => post(API_COMMENTS, {{ id, text: box.value }}), 800);
  }});
}});

applyFilters();
loadAll();
</script>
</body>
</html>"""

    out = DATA / "visualizar.html"
    out.write_text(html)
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
