"""Gera data/analise.html — versão completa pra auditoria.

Estrutura:
  1. Resumo no topo (compráveis/médios/descartados + custo)
  2. LEGENDA explicando cada categoria, tipo, tier e motivo de exclusão
  3. Itens agrupados em duas dimensões:
     - Comprável / Médio (drill por categoria)
     - Descartado (drill por MOTIVO da exclusão, pra auditar onde errou)
"""
import json
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


LEGENDAS = {
    # Tipos
    "tipo:liso": "Short de cor sólida, sem padrão gráfico. É o que queremos.",
    "tipo:estampado": "Tecido com padrão repetido (floral, listras totais, etc). Não revende.",
    "tipo:logo_grande": "SUNDEK escrito gigante na perna. Coleção moderna, não tem mercado.",
    "tipo:desbotado": "Tecido com aparência de muito uso/lavagem.",
    "tipo:nao_short": "Não é short (sunga, camiseta, calça, etc). Detectado por título ou foto.",
    "tipo:tamanho_invalido": "É short, mas tamanho fora do range comercial (W29, W30, W36, XS, XXL, etc).",
    "tipo:infantil": "Short infantil (taille X ans, tg X anni, bambino, kids, etc.) — não revendemos.",
    "tipo:nao_sundek": "Não é da marca Sundek (Nike, Adidas, etc).",
    "tipo:indefinido": "Foto borrada ou ângulo ruim, modelo não conseguiu decidir.",
    # Motivos de exclusão
    "estampado": "Tecido tem padrão gráfico cobrindo todo o corpo.",
    "logo_grande": "Palavra SUNDEK escrita em letras enormes na perna.",
    "desbotado": "Aparência envelhecida/lavada.",
    "nao_short": "Não é short — detectado pelo prefilter (palavra no título) ou pela foto.",
    "nao_short-visual": "Foto mostra sunga, slip, calça ou outra peça que não é short.",
    "nao_sundek": "Marca diferente identificada pelo modelo.",
    "cor_ruim": "Cor sem apelo comercial (neon, fluo, berrante, etc).",
    "combinacao_listra_cor_ruim": "A cor sozinha era aceitável, mas a combinação com a listra (rara/destoante) derrubou pra ruim.",
    "tecido_brilhoso": "Tecido reflexivo/acetinado (wet look).",
    "bicolor": "Dois painéis grandes de cores diferentes no corpo (não vende bem).",
    "bolso_frontal": "Bolso grande tipo cargo na frente/lateral da perna.",
    "listra_na_frente": "Listras no painel frontal (vai além das laterais).",
    "sem_bolso_traseiro": "Modelo sem bolso traseiro (vende mal).",
    "bolso_so_logo_colecao_antiga": "Bolso traseiro tem patch sem nome 'SUNDEK' escrito — coleção antiga.",
    "sem_listra_sundek": "Liso sem listra Sundek autêntica.",
    "piping_nao_e_listra_sundek": "Tem listra única (piping de costura), não a listra arco-íris real.",
    "fechamento_botao": "Tem botão no fly (estilo boardshort antigo).",
    "fechamento_velcro": "Tem velcro no fly.",
    "tamanho_XS": "Tamanho XS (não temos demanda).",
    "tamanho_XXL": "Tamanho XXL (não temos demanda).",
    # Tiers de cor
    "tier:maravilhoso": "Cores TOP: preto, branco, azul marinho. Vendem sozinhas.",
    "tier:muito_boa": "Cinza (qualquer tom).",
    "tier:boa": "Azul médio, verde escuro/militar, kaki escuro.",
    "tier:ok": "Aceitável com elástico/etiqueta. Azul claro, verde médio, laranja terroso, salmão, bege, etc.",
    "tier:ruim": "Cores neon/fluo/berrantes ou patches metálicos. Excluído.",
}

TIPO_LABELS = {
    "liso": "Liso (candidato a comprável)",
    "estampado": "Estampado",
    "logo_grande": "Logo SUNDEK gigante",
    "desbotado": "Desbotado",
    "nao_short": "Não é short",
    "tamanho_invalido": "Short com tamanho fora do range",
    "nao_sundek": "Não é da marca Sundek",
    "indefinido": "Indefinido (foto ruim)",
}


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())
    # Acervo acumula histórico; o site mostra só o que ainda está à venda.
    total_acervo = len(itens)
    itens = [x for x in itens if x.get("status") not in ("vendido", "inativo")]
    inativos = total_acervo - len(itens)
    if inativos:
        print(f"  {inativos} itens vendidos/inativos ocultados ({total_acervo} no acervo).")

    # Tenta carregar custo
    custo_total = 0.0
    try:
        custo = json.loads((DATA / "custo_por_etapa.json").read_text())
        PRECOS = {"gpt-4o-mini": {"in": 0.15, "out": 0.60},
                  "gpt-4o": {"in": 2.50, "out": 10.00}}
        for mods in custo.values():
            for m, d in mods.items():
                p = PRECOS.get(m, {"in": 0, "out": 0})
                custo_total += (d["in"] / 1e6) * p["in"] + (d["out"] / 1e6) * p["out"]
    except Exception:
        pass

    # Conta por decisão
    visiveis = [it for it in itens if not it.get("manual_exclusao")]
    dec = Counter((it.get("score") or {}).get("decisao", "?") for it in visiveis)
    compraveis = [it for it in visiveis if (it.get("score") or {}).get("decisao") == "compravel"]
    medios = [it for it in visiveis if (it.get("score") or {}).get("decisao") == "medio"]
    descartados = [it for it in visiveis if (it.get("score") or {}).get("decisao") == "descartado"]
    # Itens que FALHARAM ao classificar (cota/rede) — não foram julgados, só reprocessar.
    nao_classificados = [it for it in visiveis if (it.get("score") or {}).get("decisao") == "nao_classificado"]

    # Conta por motivo de exclusão
    motivos = Counter()
    motivo_itens: dict[str, list] = {}
    for it in descartados:
        m = (it.get("score") or {}).get("motivo_exclusao", "") or ""
        # cada item pode ter vários motivos
        for cod in m.split(", "):
            cod = cod.strip()
            if not cod:
                cod = "sem_motivo"
            motivos[cod] += 1
            motivo_itens.setdefault(cod, []).append(it)

    # Conta por tipo
    tipos = Counter((it.get("classificacao") or {}).get("tipo", "?") for it in visiveis)

    def card(it: dict, mostrar_score=True) -> str:
        cl = it.get("classificacao") or {}
        cor_raw = it.get("cor") or {}
        cor = cor_raw if isinstance(cor_raw, dict) else {}
        el = it.get("elastico") or {}
        et = it.get("etiqueta") or {}
        s = it.get("score") or {}
        fotos = (it.get("fotos") or [])[:6]
        foto = fotos[0] if fotos else ""
        outras = "".join(f'<img src="{u}" loading="lazy">' for u in fotos[1:])
        titulo = escape(it.get("titulo") or "")[:55]
        preco = escape(it.get("preco") or "?")
        tam = escape(it.get("tamanho") or "?")
        url = escape(it.get("url") or "#")

        tags = []
        tipo = cl.get("tipo")
        if tipo:
            tags.append(f'<span class="tag tipo">{escape(tipo)}</span>')
        if cor.get("tier_final") or cor.get("tier"):
            t = escape(cor.get("tier_final") or cor.get("tier") or "")
            nome = escape(cor.get("cor_principal") or "")
            tags.append(f'<span class="tag cor-{t}">{nome} · {t}</span>')
        listra = cl.get("tem_listra_lateral_sundek")
        if listra is True:
            tags.append('<span class="tag ok">listra Sundek</span>')
        elif cl.get("e_piping"):
            tags.append('<span class="tag x">piping (não listra)</span>')
        elif listra is False:
            tags.append('<span class="tag x">sem listra</span>')
        bolso = cl.get("tem_bolso_traseiro")
        nome = cl.get("bolso_traseiro_tem_nome")
        if bolso is True and nome is True:
            tags.append('<span class="tag ok">bolso + nome</span>')
        elif bolso is True and nome is False:
            tags.append('<span class="tag x">bolso só logo</span>')
        elif bolso is False:
            tags.append('<span class="tag x">sem bolso traseiro</span>')
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
            tags.append('<span class="tag ok">etiqueta</span>')

        score_html = ""
        if mostrar_score:
            score_html = f'<span class="score">score <b>{s.get("score", 0)}</b></span>'

        ev = []
        if cl.get("listra_evidencia"):
            ev.append(f"<b>listra:</b> {escape(cl['listra_evidencia'])}")
        if cl.get("bolso_evidencia"):
            ev.append(f"<b>bolso:</b> {escape(cl['bolso_evidencia'])}")
        if el.get("evidencia"):
            ev.append(f"<b>elástico:</b> {escape(el['evidencia'])}")
        evid = "<br>".join(ev)

        motivo = (s.get("motivo_exclusao") or "") or (s.get("motivo") or "")
        motivo_html = f'<div class="motivo">{escape(motivo)}</div>' if motivo else ''

        item_id = escape(str(it.get("id") or ""))
        return f"""<div class="card" data-id="{item_id}">
  <div class="thumbs"><img src="{foto}" loading="lazy" class="main">{outras}</div>
  <div class="info">
    <a href="{url}" target="_blank" class="t">{titulo}</a>
    <div class="meta">{preco} · {tam} · {score_html}</div>
    <div class="tags">{''.join(tags)}</div>
    {motivo_html}
    <div class="evid">{evid}</div>
    <div class="feedback">
      <button class="disagree-btn" data-id="{item_id}">⚠ Discordo</button>
      <textarea class="disagree-text" data-id="{item_id}" placeholder="(opcional) O que está errado?"></textarea>
      <div class="status" data-id="{item_id}"></div>
    </div>
  </div>
</div>"""

    # Legenda HTML
    leg_tipos = "".join(
        f'<tr><td><span class="tag tipo">{escape(k.replace("tipo:",""))}</span></td><td>{escape(v)}</td></tr>'
        for k, v in LEGENDAS.items() if k.startswith("tipo:")
    )
    leg_tiers = "".join(
        f'<tr><td><span class="tag cor-{k.replace("tier:","")}">{escape(k.replace("tier:",""))}</span></td><td>{escape(v)}</td></tr>'
        for k, v in LEGENDAS.items() if k.startswith("tier:")
    )
    leg_motivos = "".join(
        f'<tr><td><code>{escape(k)}</code></td><td>{escape(v)}</td></tr>'
        for k, v in LEGENDAS.items() if not k.startswith(("tipo:", "tier:"))
    )

    # Seções
    secoes = []

    # Compráveis
    if compraveis:
        cards = "\n".join(card(it) for it in sorted(compraveis, key=lambda x: -(x.get("score") or {}).get("score", 0)))
        secoes.append(f"""<details class="grupo" open>
  <summary><span class="cnt cnt-ok">✓ {len(compraveis)}</span> COMPRÁVEIS</summary>
  <div class="lista">{cards}</div>
</details>""")

    # Médios (barganha)
    if medios:
        cards = "\n".join(card(it) for it in sorted(medios, key=lambda x: -(x.get("score") or {}).get("score", 0)))
        secoes.append(f"""<details class="grupo" open>
  <summary><span class="cnt cnt-mid">~ {len(medios)}</span> BARGANHA (médios)</summary>
  <div class="lista">{cards}</div>
</details>""")

    # Descartados — agrupado por motivo
    sub_motivos = []
    for cod, lista in sorted(motivo_itens.items(), key=lambda x: -len(x[1])):
        cards = "\n".join(card(it, mostrar_score=False) for it in lista[:80])
        mais = "" if len(lista) <= 80 else f'<div class="more">+ {len(lista) - 80} itens</div>'
        legenda = LEGENDAS.get(cod, "—")
        sub_motivos.append(f"""<details class="sub">
  <summary><span class="cnt-sub">{len(lista)}</span> <code>{escape(cod)}</code> <span class="leg">— {escape(legenda)}</span></summary>
  <div class="lista">{cards}</div>
  {mais}
</details>""")

    secoes.append(f"""<details class="grupo">
  <summary><span class="cnt cnt-x">✗ {len(descartados)}</span> DESCARTADOS (clique para auditar por motivo)</summary>
  <div class="subs">{''.join(sub_motivos)}</div>
</details>""")

    # Não classificados (falha de cota/rede) — separados dos descartados
    if nao_classificados:
        cards = "\n".join(card(it, mostrar_score=False) for it in nao_classificados[:120])
        mais = "" if len(nao_classificados) <= 120 else f'<div class="more">+ {len(nao_classificados) - 120} itens</div>'
        secoes.append(f"""<details class="grupo">
  <summary><span class="cnt" style="background:#92400e">⟳ {len(nao_classificados)}</span> NÃO CLASSIFICADOS (falha de cota/rede — serão reprocessados)</summary>
  <div class="lista">{cards}</div>
  {mais}
</details>""")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Análise</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#f2f2f0; color:#18181b; padding:20px 14px 60px; }}
.container {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:24px; margin-bottom:6px; }}
h2 {{ font-size:16px; margin:16px 0 8px; color:#52525b; }}
.sub-h {{ color:#666; font-size:13px; margin-bottom:18px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:10px; margin-bottom:20px; }}
.stat {{ background:#fff; border:1px solid #e4e4e7; border-radius:10px; padding:12px; }}
.stat .v {{ font-size:22px; font-weight:700; color:#18181b; }}
.stat .l {{ font-size:12px; color:#71717a; margin-top:4px; }}
.stat.ok .v {{ color:#15803d; }}
.stat.mid .v {{ color:#a16207; }}
.stat.x .v {{ color:#7f1d1d; }}

.legenda {{ background:#fff; border:1px solid #e4e4e7; border-radius:10px;
  padding:14px; margin-bottom:20px; }}
.legenda summary {{ cursor:pointer; font-weight:600; padding:4px 0; user-select:none; }}
.legenda table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
.legenda td {{ padding:6px 8px; border-bottom:1px solid #f3f4f6; font-size:13px;
  vertical-align:top; }}
.legenda td:first-child {{ width:22%; }}
.legenda code {{ background:#f4f4f5; padding:1px 5px; border-radius:3px;
  font-size:11px; color:#52525b; }}

details {{ background:#fff; border:1px solid #e4e4e7; border-radius:10px;
  margin-bottom:12px; overflow:hidden; }}
details.sub {{ background:#fafafa; border:1px solid #ececec; margin:8px; }}
summary {{ cursor:pointer; padding:14px 16px; font-weight:600;
  list-style:none; display:flex; align-items:center; gap:10px; font-size:15px; }}
summary::-webkit-details-marker {{ display:none; }}
summary::before {{ content:"▸"; color:#999; font-size:13px; transition:transform .15s; }}
details[open]>summary::before {{ transform:rotate(90deg); }}
details.sub summary {{ padding:10px 14px; font-size:13px; font-weight:500; }}

.cnt {{ display:inline-flex; align-items:center; justify-content:center;
  min-width:32px; padding:3px 10px; border-radius:99px;
  font-size:13px; font-weight:700; background:#18181b; color:#fff; }}
.cnt-ok {{ background:#15803d; }}
.cnt-mid {{ background:#a16207; }}
.cnt-x {{ background:#7f1d1d; }}
.cnt-sub {{ background:#6b7280; color:#fff; font-size:12px;
  padding:2px 8px; border-radius:99px; min-width:28px; text-align:center; }}
.leg {{ color:#71717a; font-size:12px; font-weight:400; }}

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
.score {{ background:#f4f4f5; padding:1px 7px; border-radius:5px;
  font-size:11px; color:#52525b; }}
.tags {{ display:flex; flex-wrap:wrap; gap:4px; margin:6px 0; }}
.tag {{ font-size:11px; padding:2px 7px; border-radius:99px;
  background:#eee; color:#333; }}
.tag.tipo {{ background:#dbeafe; color:#1e3a8a; }}
.tag.ok {{ background:#dcfce7; color:#14532d; }}
.tag.x {{ background:#fee2e2; color:#7f1d1d; }}
.tag.mid {{ background:#fef9c3; color:#713f12; }}
.tag.cor-maravilhoso {{ background:#fbcfe8; color:#831843; }}
.tag.cor-muito_boa {{ background:#bbf7d0; color:#14532d; }}
.tag.cor-boa {{ background:#bae6fd; color:#0c4a6e; }}
.tag.cor-ok {{ background:#fde68a; color:#713f12; }}
.tag.cor-ruim {{ background:#fecaca; color:#7f1d1d; }}
.motivo {{ color:#7f1d1d; font-size:12px; font-style:italic; margin-top:4px; }}
.evid {{ color:#666; font-size:11px; line-height:1.5; margin-top:6px;
  padding-top:6px; border-top:1px dashed #ddd; }}
.evid b {{ color:#333; }}
.more {{ padding:8px 14px; color:#999; font-size:12px; }}

.feedback {{ margin-top:10px; padding-top:8px; border-top:1px dashed #ddd; }}
.disagree-btn {{ background:#fff; border:1px solid #d4d4d8; color:#52525b;
  padding:5px 10px; border-radius:6px; font-size:12px; cursor:pointer; }}
.disagree-btn:hover {{ background:#fef2f2; border-color:#fca5a5; color:#7f1d1d; }}
.disagree-btn.active {{ background:#fee2e2; border-color:#ef4444; color:#7f1d1d; }}
.disagree-text {{ display:none; width:100%; margin-top:6px; padding:6px 8px;
  font-size:12px; border:1px solid #fca5a5; border-radius:6px; resize:vertical;
  min-height:42px; font-family:inherit; }}
.disagree-text.visible {{ display:block; }}
.status {{ font-size:11px; color:#16a34a; margin-top:4px; min-height:14px; }}
</style></head><body>
<div class="container">

<h1>Didi · Análise da rodada</h1>
<div class="sub-h">{len(itens)} itens no scrape, {sum(dec.values())} processados.
  Custo total estimado: <b>${custo_total:.2f}</b> (~R$ {custo_total*5:.2f}).</div>

<div class="stats">
  <div class="stat ok"><div class="v">{dec.get('compravel', 0)}</div><div class="l">Compráveis</div></div>
  <div class="stat mid"><div class="v">{dec.get('medio', 0)}</div><div class="l">Barganha (médios)</div></div>
  <div class="stat x"><div class="v">{dec.get('descartado', 0)}</div><div class="l">Descartados</div></div>
  <div class="stat"><div class="v" style="color:#92400e">{dec.get('nao_classificado', 0)}</div><div class="l">Não classificados (reprocessar)</div></div>
  <div class="stat"><div class="v">{tipos.get('liso', 0)}</div><div class="l">Lisos detectados</div></div>
  <div class="stat"><div class="v">{tipos.get('estampado', 0) + tipos.get('logo_grande', 0)}</div><div class="l">Estampados / Logo</div></div>
  <div class="stat"><div class="v">{tipos.get('nao_short', 0) + tipos.get('nao_sundek', 0)}</div><div class="l">Não-short / Não-Sundek</div></div>
</div>

<details class="legenda">
  <summary>📖 Legenda — clique pra entender cada categoria</summary>
  <h2>Tipo do short (decisão inicial)</h2>
  <table>{leg_tipos}</table>
  <h2>Tier de cor (mercado brasileiro)</h2>
  <table>{leg_tiers}</table>
  <h2>Motivos de exclusão automática</h2>
  <table>{leg_motivos}</table>
</details>

<h2>Itens classificados</h2>
{''.join(secoes)}

</div>
<script>
const API = 'https://votacao-two.vercel.app/api';
const NS = 'analise:';
async function loadAll() {{
  try {{
    const [rc, rr] = await Promise.all([fetch(API+'/comments'), fetch(API+'/reactions')]);
    const cm = await rc.json(); const rx = await rr.json();
    document.querySelectorAll('.card').forEach(card => {{
      const k = NS + card.dataset.id;
      const t = cm[k]; const r = rx[k]?.reaction;
      if (t) {{ const ta = card.querySelector('.disagree-text'); ta.value = t; ta.classList.add('visible'); }}
      if (r === 'discordo') {{
        const b = card.querySelector('.disagree-btn');
        b.classList.add('active'); b.textContent = '⚠ Discordo (marcado)';
        card.querySelector('.disagree-text').classList.add('visible');
      }}
    }});
  }} catch(e) {{ console.warn(e); }}
}}
const timers = {{}};
function status(card, msg, ok=true) {{
  const el = card.querySelector('.status');
  el.textContent = msg; el.style.color = ok ? '#16a34a' : '#dc2626';
  setTimeout(() => {{ if (el.textContent === msg) el.textContent = ''; }}, 2500);
}}
async function post(url, body) {{
  return fetch(url, {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body) }});
}}
document.querySelectorAll('.disagree-btn').forEach(b => {{
  b.addEventListener('click', async () => {{
    const card = b.closest('.card');
    const k = NS + b.dataset.id;
    const a = b.classList.toggle('active');
    b.textContent = a ? '⚠ Discordo (marcado)' : '⚠ Discordo';
    card.querySelector('.disagree-text').classList.toggle('visible', a);
    try {{ await post(API+'/reactions', {{ id: k, reaction: a ? 'discordo' : null }}); status(card, a?'marcado':'desmarcado'); }}
    catch(e) {{ status(card, 'erro', false); }}
  }});
}});
document.querySelectorAll('.disagree-text').forEach(ta => {{
  ta.addEventListener('input', () => {{
    const card = ta.closest('.card');
    const k = NS + ta.dataset.id;
    clearTimeout(timers[ta.dataset.id]);
    timers[ta.dataset.id] = setTimeout(async () => {{
      try {{ await post(API+'/comments', {{ id: k, text: ta.value }}); status(card, 'salvo'); }}
      catch(e) {{ status(card, 'erro', false); }}
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
