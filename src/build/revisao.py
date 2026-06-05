"""Gera votacao/public/revisao.html — AUDITORIA dos descartados (por que caíram).

Agrupa os descartados por MOTIVO, mostra foto + motivo + breakdown do score, e um
botão "⚠️ classificação errada" + comentário pra sinalizar erros (salva em
/api/reactions, namespace 'revisao:'). Só Sundek.

Uso: python -m src.build.revisao
"""
import json
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "votacao" / "public" / "revisao.html"
API = "https://votacao-two.vercel.app/api"
NS = "revisao:"

LEGENDAS = {
    "sem_elastico_cor_fraca": "Sem elástico e cor fora de preto/branco/azul marinho.",
    "sem_listra_sundek": "Liso sem a listra Sundek autêntica.",
    "piping_nao_e_listra_sundek": "Tem piping de costura, não a listra real.",
    "cor_ruim": "Cor sem apelo (neon/fluo) — avaliada.",
    "combinacao_listra_cor_ruim": "Cor ok mas a combinação com a listra ficou ruim.",
    "estampado": "Estampa cobrindo o corpo.",
    "logo_grande": "SUNDEK escrito gigante na perna.",
    "desbotado": "Aparência gasta/suja/desbotada.",
    "nao_short": "Não é short.",
    "nao_sundek": "Não é da marca Sundek.",
    "tamanho_invalido": "Tamanho fora do range.",
    "tamanho_XS": "Tamanho XS.",
    "tamanho_XXL": "Tamanho XXL.",
    "bolso_so_logo_colecao_antiga": "Bolso só com logo (sem nome SUNDEK) — coleção antiga.",
    "sem_bolso_traseiro": "Sem bolso traseiro.",
    "bicolor": "Dois painéis grandes de cores diferentes.",
    "tecido_brilhoso": "Tecido brilhoso/acetinado.",
    "bolso_frontal": "Bolso cargo na frente.",
    "fechamento_botao": "Botão no fly (boardshort antigo).",
    "fechamento_velcro": "Velcro no fly.",
    "infantil": "Short infantil.",
}


def _card(it: dict) -> str:
    s = it.get("score") or {}
    cl = it.get("classificacao") or {}
    cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
    fotos = (it.get("fotos") or [])[:6]
    titulo = escape((it.get("titulo") or "")[:60])
    preco = escape(it.get("preco_total") or it.get("preco") or "?")
    tam = escape(it.get("tamanho") or "?")
    url = escape(it.get("url") or "#")
    iid = escape(str(it.get("id") or ""))
    cor_txt = escape(f"{cor.get('cor_principal') or '?'} / {cor.get('tier_final') or cor.get('tier') or '?'}")
    por_que = escape((s.get("motivo_exclusao") or s.get("motivo") or "").strip())

    imgs = "".join(f'<img src="{escape(u)}" loading="lazy"{"" if i == 0 else " hidden"}>'
                   for i, u in enumerate(fotos))
    setas = ('<button class="nav prev">‹</button><button class="nav next">›</button>'
             '<span class="count"></span>') if len(fotos) > 1 else ""

    return f"""<div class="card" data-id="{iid}">
  <div class="ph">{imgs}{setas}</div>
  <div class="body">
    <a class="t" href="{url}" target="_blank" rel="noreferrer">{titulo}</a>
    <div class="meta">{tam} · {preco} · {cor_txt}</div>
    <div class="motivo">✗ {por_que}</div>
    <div class="vote">
      <button class="v err" data-r="errado">⚠️ Classificação errada</button>
    </div>
    <textarea class="obs" rows="2" placeholder="O que está errado? (ex: tem listra sim, no traseiro)"></textarea>
    <div class="status"></div>
  </div>
</div>"""


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())
    itens = [x for x in itens if x.get("status") not in ("vendido", "inativo")]
    desc = [x for x in itens if (x.get("score") or {}).get("decisao") == "descartado"]

    # agrupa por motivo (1º motivo de cada item)
    grupos: dict[str, list] = {}
    for it in desc:
        m = ((it.get("score") or {}).get("motivo_exclusao") or "outro").split(", ")[0].strip() or "outro"
        grupos.setdefault(m, []).append(it)

    secoes = []
    for motivo, lista in sorted(grupos.items(), key=lambda x: -len(x[1])):
        leg = LEGENDAS.get(motivo, "")
        cards = "\n".join(_card(it) for it in lista[:60])
        mais = "" if len(lista) <= 60 else f'<div class="more">+ {len(lista)-60} itens</div>'
        secoes.append(f"""<details class="grupo">
  <summary><span class="cnt">{len(lista)}</span> <code>{escape(motivo)}</code>
    <span class="leg">{escape(leg)}</span></summary>
  <div class="grid">{cards}</div>{mais}
</details>""")

    dec = Counter((x.get("score") or {}).get("decisao") for x in itens)
    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Sundek · Revisão dos descartados</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#0e0e12; color:#f5f5f7; padding:16px 12px 60px; }}
.wrap {{ max-width:900px; margin:0 auto; }}
h1 {{ font-size:20px; margin-bottom:4px; }}
.sub {{ color:#b8b8c0; font-size:13px; margin-bottom:16px; }}
details.grupo {{ background:#15151b; border:1px solid rgba(255,255,255,.08); border-radius:12px; margin-bottom:10px; overflow:hidden; }}
summary {{ cursor:pointer; padding:12px 14px; font-size:14px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; list-style:none; }}
summary::-webkit-details-marker {{ display:none; }}
.cnt {{ background:#ff4d6d; color:#fff; border-radius:99px; padding:2px 9px; font-size:12px; font-weight:700; }}
code {{ background:rgba(255,255,255,.06); padding:1px 6px; border-radius:5px; font-size:12px; color:#ffcc66; }}
.leg {{ color:#9a9aa6; font-size:12px; }}
.grid {{ display:grid; grid-template-columns:1fr; gap:12px; padding:6px 12px 14px; }}
@media(min-width:640px) {{ .grid {{ grid-template-columns:1fr 1fr; }} }}
@media(min-width:900px) {{ .grid {{ grid-template-columns:1fr 1fr 1fr; }} }}
.card {{ background:#17171d; border:1px solid rgba(255,255,255,.08); border-radius:14px; overflow:hidden; }}
.ph {{ position:relative; width:100%; aspect-ratio:1; background:#0b0b0f; }}
.ph img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.ph img[hidden] {{ display:none; }}
.nav {{ position:absolute; top:50%; transform:translateY(-50%); width:34px; height:34px; border:none; border-radius:50%; background:rgba(0,0,0,.45); color:#fff; font-size:20px; cursor:pointer; }}
.nav.prev {{ left:6px; }} .nav.next {{ right:6px; }}
.count {{ position:absolute; top:6px; right:6px; background:rgba(0,0,0,.5); color:#fff; font-size:10px; padding:1px 6px; border-radius:99px; }}
.body {{ padding:10px; display:flex; flex-direction:column; gap:6px; }}
.t {{ color:#f5f5f7; text-decoration:none; font-size:13px; line-height:1.3; }}
.meta {{ color:#b8b8c0; font-size:12px; }}
.motivo {{ color:#ff8095; font-size:12px; font-style:italic; }}
.v.err {{ width:100%; padding:8px; border:1px solid rgba(255,170,0,.4); border-radius:9px; background:rgba(255,170,0,.08); color:#ffcc66; font-size:12px; font-weight:600; cursor:pointer; }}
.v.err.sel {{ background:#ffaa00; color:#1c1100; }}
.obs {{ width:100%; padding:8px; border-radius:9px; resize:vertical; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); color:#f5f5f7; font-size:14px; font-family:inherit; }}
.obs::placeholder {{ color:#7a7a86; }}
.obs:focus {{ outline:none; border-color:#00d9ff; }}
.status {{ font-size:11px; color:#00d9ff; min-height:13px; }}
.more {{ padding:0 14px 12px; color:#9a9aa6; font-size:12px; }}
</style></head><body>
<div class="wrap">
  <h1>Sundek · Revisão dos descartados</h1>
  <div class="sub">{len(desc)} descartados de {len(itens)} (compráveis {dec.get('compravel',0)} · barganha {dec.get('medio',0)}).
    Abra um motivo, confira as fotos, e marque "⚠️ errada" + comentário onde achar que o robô errou.</div>
  {''.join(secoes)}
</div>
<script>
const API="{API}", NS="{NS}";
fetch(API+"/reactions").then(r=>r.json()).then(data=>{{
  document.querySelectorAll(".card").forEach(c=>{{
    const v=data[NS+c.dataset.id]; if(!v) return;
    if(v.reaction==="errado"){{ c.querySelector(".v.err").classList.add("sel"); }}
    if(v.observacao){{ c.querySelector(".obs").value=v.observacao; }}
  }});
}}).catch(()=>{{}});
document.querySelectorAll(".card").forEach(card=>{{
  const imgs=[...card.querySelectorAll(".ph img")], cnt=card.querySelector(".count"); let idx=0;
  const show=i=>{{ idx=(i+imgs.length)%imgs.length; imgs.forEach((im,j)=>im.hidden=j!==idx); if(cnt)cnt.textContent=(idx+1)+"/"+imgs.length; }};
  if(imgs.length>1){{ show(0);
    card.querySelector(".prev").onclick=()=>show(idx-1); card.querySelector(".next").onclick=()=>show(idx+1);
    let x0=null; const ph=card.querySelector(".ph");
    ph.addEventListener("touchstart",e=>x0=e.touches[0].clientX,{{passive:true}});
    ph.addEventListener("touchend",e=>{{ if(x0==null)return; const dx=e.changedTouches[0].clientX-x0; if(Math.abs(dx)>35)show(idx+(dx<0?1:-1)); x0=null; }});
  }}
  const st=card.querySelector(".status");
  card.querySelector(".v.err").onclick=async function(){{
    const sel=this.classList.toggle("sel"); st.textContent="salvando…";
    try{{ await fetch(API+"/reactions",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:NS+card.dataset.id,reaction:sel?"errado":null}})}}); st.textContent=sel?"marcado ✓":"desmarcado"; }}catch(e){{ st.textContent="erro"; }}
    setTimeout(()=>st.textContent="",2000);
  }};
  const obs=card.querySelector(".obs");
  obs.addEventListener("blur",async()=>{{ st.textContent="salvando…";
    try{{ await fetch(API+"/reactions",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:NS+card.dataset.id,observacao:obs.value}})}}); st.textContent="comentário salvo ✓"; }}catch(e){{ st.textContent="erro"; }}
    setTimeout(()=>st.textContent="",2000);
  }});
}});
</script>
</body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"OK -> {OUT}  ({len(desc)} descartados em {len(grupos)} motivos)")


if __name__ == "__main__":
    main()
