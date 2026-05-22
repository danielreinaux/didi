"""Gera data/analise.html — TODOS os itens classificados com detalhes,
agrupados por decisão. Ideal para auditoria/análise.
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())

    def card(it: dict) -> str:
        cl = it.get("classificacao") or {}
        cor_raw = it.get("cor") or {}
        cor = cor_raw if isinstance(cor_raw, dict) else {}
        el = it.get("elastico") or {}
        et = it.get("etiqueta") or {}
        s = it.get("score") or {}

        fotos = (it.get("fotos") or [])[:8]
        foto = fotos[0] if fotos else ""
        outras = "".join(f'<img src="{u}" loading="lazy">' for u in fotos[1:])

        titulo = escape(it.get("titulo") or "")[:60]
        preco = escape(it.get("preco") or "?")
        tam = escape(it.get("tamanho") or "?")
        url = escape(it.get("url") or "#")

        tags = []
        if cl.get("tipo"):
            tags.append(f'<span class="tag tipo">{escape(cl["tipo"])}</span>')
        if cor.get("tier_final") or cor.get("tier"):
            tier = escape(cor.get("tier_final") or cor.get("tier") or "")
            cor_nome = escape(cor.get("cor_principal") or "")
            tags.append(f'<span class="tag cor-{tier}">{cor_nome} · {tier}</span>')
        listra = cl.get("tem_listra_lateral_sundek")
        if listra is True:
            cores = ", ".join(cl.get("cores_listras") or [])
            tags.append(f'<span class="tag listra">listra✓ [{escape(cores)}]</span>')
        elif listra is False:
            piping = " (piping)" if cl.get("e_piping") else ""
            tags.append(f'<span class="tag x">sem listra{piping}</span>')
        bolso = cl.get("tem_bolso_traseiro")
        nome = cl.get("bolso_traseiro_tem_nome")
        if bolso is True and nome is True:
            tags.append('<span class="tag ok">bolso+nome</span>')
        elif bolso is True and nome is False:
            tags.append('<span class="tag x">bolso só logo</span>')
        elif bolso is True and nome is None:
            tags.append('<span class="tag mid">bolso, nome?</span>')
        elif bolso is False:
            tags.append('<span class="tag x">sem bolso</span>')
        if cl.get("bicolor"):
            tags.append('<span class="tag x">bicolor</span>')
        if cl.get("tecido_brilhoso"):
            tags.append('<span class="tag x">brilhoso</span>')
        if cl.get("tem_bolso_frontal"):
            tags.append('<span class="tag x">bolso frontal</span>')
        if cl.get("listra_na_frente"):
            tags.append('<span class="tag x">listra na frente</span>')
        if el.get("tem_elastico") is True:
            tags.append('<span class="tag ok">elástico</span>')
        elif el.get("tem_elastico") is False:
            tags.append('<span class="tag mid">sem elástico</span>')
        if el.get("tipo_fechamento") in ("botao", "velcro"):
            tags.append(f'<span class="tag x">{el["tipo_fechamento"]}</span>')
        if et.get("tem_etiqueta") is True:
            tags.append('<span class="tag ok">etiqueta✓</span>')

        score_val = s.get("score", 0)
        decisao = s.get("decisao", "?")
        motivo = s.get("motivo_exclusao") or s.get("motivo") or ""

        ev_lines = []
        if cl.get("listra_evidencia"):
            ev_lines.append(f"<b>listra:</b> {escape(cl['listra_evidencia'])}")
        if cl.get("bolso_evidencia"):
            ev_lines.append(f"<b>bolso:</b> {escape(cl['bolso_evidencia'])}")
        if el.get("evidencia"):
            ev_lines.append(f"<b>elástico:</b> {escape(el['evidencia'])}")
        if cl.get("justificativa"):
            ev_lines.append(f"<b>tipo:</b> {escape(cl['justificativa'])}")
        evid = "<br>".join(ev_lines)

        item_id = escape(str(it.get("id") or ""))
        return f"""<div class="card" data-id="{item_id}">
  <div class="thumbs"><img src="{foto}" loading="lazy" class="main">{outras}</div>
  <div class="info">
    <a href="{url}" target="_blank" class="t">{titulo}</a>
    <div class="meta">{preco} · {tam} · score <b>{score_val}</b></div>
    <div class="tags">{''.join(tags)}</div>
    <div class="motivo">{escape(motivo)}</div>
    <div class="evid">{evid}</div>
    <div class="feedback">
      <button class="disagree-btn" data-id="{item_id}">⚠ Discordo da classificação</button>
      <textarea class="disagree-text" data-id="{item_id}"
        placeholder="(opcional) O que está errado? Ex: tem nome SUNDEK no patch, não é bicolor, etc."></textarea>
      <div class="status" data-id="{item_id}"></div>
    </div>
  </div>
</div>"""

    grupos = {
        "compravel": ("✓ Comprável", []),
        "medio": ("~ Médio/Barganha", []),
        "descartado": ("✗ Descartado", []),
    }
    sem_decisao = []
    for it in itens:
        if it.get("manual_exclusao"):
            continue
        d = (it.get("score") or {}).get("decisao")
        if d in grupos:
            grupos[d][1].append(it)
        else:
            sem_decisao.append(it)

    secoes = []
    for key, (label, lista) in grupos.items():
        if not lista:
            continue
        # ordena por score desc dentro do grupo
        lista.sort(key=lambda x: -(x.get("score") or {}).get("score", 0))
        cards = "\n".join(card(it) for it in lista)
        secoes.append(f"""<details class="grupo" open>
  <summary><span class="cnt">{len(lista)}</span> {escape(label)}</summary>
  <div class="lista">{cards}</div>
</details>""")
    if sem_decisao:
        cards = "\n".join(card(it) for it in sem_decisao)
        secoes.append(f"""<details class="grupo">
  <summary><span class="cnt">{len(sem_decisao)}</span> Sem decisão</summary>
  <div class="lista">{cards}</div>
</details>""")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Análise completa</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#f2f2f0; color:#18181b; padding:20px 14px 60px; }}
.container {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub {{ color:#666; font-size:13px; margin-bottom:20px; }}
details {{ background:#fff; border:1px solid #e0e0e0; border-radius:10px;
  margin-bottom:12px; overflow:hidden; }}
summary {{ cursor:pointer; padding:14px 16px; font-weight:600; font-size:15px;
  list-style:none; display:flex; align-items:center; gap:10px; }}
summary::-webkit-details-marker {{ display:none; }}
summary::before {{ content:"▸"; color:#999; font-size:13px; transition:transform .15s; }}
details[open]>summary::before {{ transform:rotate(90deg); }}
.cnt {{ background:#18181b; color:#fff; border-radius:99px; padding:2px 9px;
  font-size:13px; font-weight:700; }}
.lista {{ padding:6px 14px 14px; display:flex; flex-direction:column; gap:10px; }}
.card {{ display:flex; gap:12px; background:#fafafa; border:1px solid #ececec;
  border-radius:8px; padding:10px; }}
.thumbs {{ display:flex; gap:4px; flex-wrap:wrap; width:280px; flex-shrink:0; }}
.thumbs img {{ width:64px; height:64px; object-fit:cover; border-radius:5px; background:#eee; }}
.thumbs img.main {{ width:132px; height:132px; }}
.info {{ flex:1; min-width:0; }}
.t {{ font-weight:600; color:#18181b; text-decoration:none; font-size:14px; line-height:1.3; }}
.t:hover {{ text-decoration:underline; }}
.meta {{ color:#444; font-size:13px; margin:4px 0; }}
.tags {{ display:flex; flex-wrap:wrap; gap:4px; margin:6px 0; }}
.tag {{ font-size:11px; padding:2px 7px; border-radius:99px; background:#eee; color:#333; }}
.tag.tipo {{ background:#dbeafe; color:#1e3a8a; }}
.tag.ok {{ background:#dcfce7; color:#14532d; }}
.tag.x  {{ background:#fee2e2; color:#7f1d1d; }}
.tag.mid {{ background:#fef9c3; color:#713f12; }}
.tag.listra {{ background:#e0e7ff; color:#3730a3; }}
.tag.cor-maravilhoso {{ background:#fbcfe8; color:#831843; }}
.tag.cor-muito_boa {{ background:#bbf7d0; color:#14532d; }}
.tag.cor-boa {{ background:#bae6fd; color:#0c4a6e; }}
.tag.cor-ok {{ background:#fde68a; color:#713f12; }}
.tag.cor-ruim {{ background:#fecaca; color:#7f1d1d; }}
.motivo {{ color:#7f1d1d; font-size:12px; font-style:italic; margin-top:4px; }}
.evid {{ color:#666; font-size:11px; line-height:1.5; margin-top:6px; padding-top:6px;
  border-top:1px dashed #ddd; }}
.evid b {{ color:#333; }}
.feedback {{ margin-top:10px; padding-top:8px; border-top:1px dashed #ddd; }}
.disagree-btn {{ background:#fff; border:1px solid #d4d4d8; color:#52525b;
  padding:5px 10px; border-radius:6px; font-size:12px; cursor:pointer;
  font-weight:500; transition: all .15s; }}
.disagree-btn:hover {{ background:#fef2f2; border-color:#fca5a5; color:#7f1d1d; }}
.disagree-btn.active {{ background:#fee2e2; border-color:#ef4444; color:#7f1d1d; }}
.disagree-text {{ display:none; width:100%; margin-top:6px; padding:6px 8px;
  font-size:12px; border:1px solid #fca5a5; border-radius:6px; resize:vertical;
  min-height:42px; font-family:inherit; }}
.disagree-text.visible {{ display:block; }}
.status {{ font-size:11px; color:#16a34a; margin-top:4px; min-height:14px; }}
</style></head><body>
<div class="container">
<h1>Análise — itens classificados</h1>
<div class="sub">Auditoria completa. Cada card mostra fotos, tags, decisão, motivo de exclusão e evidências. Marque <b>"Discordo"</b> nos que estiverem com classificação errada — fica salvo pra revisão.</div>
{''.join(secoes)}
</div>
<script>
const API = 'https://votacao-two.vercel.app/api';
const NS = 'analise:';  // prefixo pra separar dos comentários do viewer

async function loadAll() {{
  try {{
    const [rCom, rRea] = await Promise.all([
      fetch(API + '/comments'),
      fetch(API + '/reactions')
    ]);
    const comments = await rCom.json();
    const reactions = await rRea.json();
    document.querySelectorAll('.card').forEach(card => {{
      const id = card.dataset.id;
      const key = NS + id;
      const txt = comments[key];
      const reaction = reactions[key]?.reaction;
      if (txt) {{
        const ta = card.querySelector('.disagree-text');
        ta.value = txt;
        ta.classList.add('visible');
      }}
      if (reaction === 'discordo') {{
        const btn = card.querySelector('.disagree-btn');
        btn.classList.add('active');
        btn.textContent = '⚠ Discordo (marcado)';
        card.querySelector('.disagree-text').classList.add('visible');
      }}
    }});
  }} catch (e) {{ console.warn('Erro ao carregar feedbacks', e); }}
}}

const saveTimers = {{}};
function setStatus(card, msg, ok=true) {{
  const el = card.querySelector('.status');
  el.textContent = msg;
  el.style.color = ok ? '#16a34a' : '#dc2626';
  setTimeout(() => {{ if (el.textContent === msg) el.textContent = ''; }}, 2500);
}}

async function post(url, body) {{
  return fetch(url, {{
    method:'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(body)
  }});
}}

document.querySelectorAll('.disagree-btn').forEach(btn => {{
  btn.addEventListener('click', async () => {{
    const card = btn.closest('.card');
    const id = btn.dataset.id;
    const key = NS + id;
    const ativo = btn.classList.toggle('active');
    btn.textContent = ativo ? '⚠ Discordo (marcado)' : '⚠ Discordo da classificação';
    card.querySelector('.disagree-text').classList.toggle('visible', ativo);
    try {{
      await post(API + '/reactions', {{ id: key, reaction: ativo ? 'discordo' : null }});
      setStatus(card, ativo ? 'marcado' : 'desmarcado');
    }} catch (e) {{ setStatus(card, 'erro ao salvar', false); }}
  }});
}});

document.querySelectorAll('.disagree-text').forEach(ta => {{
  ta.addEventListener('input', () => {{
    const card = ta.closest('.card');
    const id = ta.dataset.id;
    const key = NS + id;
    clearTimeout(saveTimers[id]);
    saveTimers[id] = setTimeout(async () => {{
      try {{
        await post(API + '/comments', {{ id: key, text: ta.value }});
        setStatus(card, 'salvo');
      }} catch (e) {{ setStatus(card, 'erro ao salvar', false); }}
    }}, 700);
  }});
}});

loadAll();
</script>
</body></html>"""

    out = DATA / "analise.html"
    out.write_text(html)
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
