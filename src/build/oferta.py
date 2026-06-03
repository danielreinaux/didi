"""Gera votacao/public/oferta.html — página enxuta pra enviar pra alguém votar.

Mostra SÓ: foto(s) do short, preço, a sugestão de negociação (o que tentar, se
tentar) e os botões 👍 / 👎 / ⚠️. Vota no MESMO backend (/api/reactions) usado
pela página principal, com namespace próprio 'oferta:' pra não misturar votos.

Inclui SÓ compráveis + barganha do Sundek (Ville fica de fora desta página).
Uso: python -m src.build.oferta
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = ROOT / "votacao" / "public" / "oferta.html"
API = "https://votacao-two.vercel.app/api"
NS = "oferta:"


def _candidatos() -> list[dict]:
    # APENAS Sundek (coleta-classificada.json). Ville fica de fora desta página.
    out = []
    p = DATA / "coleta-classificada.json"
    if p.exists():
        for it in json.loads(p.read_text(encoding="utf-8")):
            s = it.get("score") or {}
            if s.get("decisao") not in ("compravel", "medio"):
                continue
            if it.get("status") in ("vendido", "inativo"):
                continue
            out.append(it)
    out.sort(key=lambda x: (
        0 if (x.get("score") or {}).get("decisao") == "compravel" else 1,
        -(x.get("score") or {}).get("score", 0),
    ))
    return out


def _card(it: dict) -> str:
    s = it.get("score") or {}
    neg = s.get("negociacao") or {}
    fotos = (it.get("fotos") or [])[:6]
    titulo = escape((it.get("titulo") or "")[:70])
    preco = escape(it.get("preco_total") or it.get("preco") or "?")
    tam = escape(it.get("tamanho") or "?")
    url = escape(it.get("url") or "#")
    iid = escape(str(it.get("id") or ""))
    compravel = s.get("decisao") == "compravel"
    badge = "✓ Comprável" if compravel else "~ Barganha"
    badge_cls = "comp" if compravel else "barg"

    imgs = "".join(f'<img src="{escape(u)}" loading="lazy" data-i="{i}"{"" if i == 0 else " hidden"}>'
                   for i, u in enumerate(fotos))
    setas = """
      <button class="nav prev" aria-label="anterior">‹</button>
      <button class="nav next" aria-label="próxima">›</button>
      <span class="count"></span>""" if len(fotos) > 1 else ""

    if neg.get("msg"):
        neg_cls = "fechar" if neg.get("modo") == "fechar" else "negociar"
        neg_html = f'<div class="neg {neg_cls}">{escape(neg["msg"])}</div>'
    else:
        neg_html = '<div class="neg none">Sem sugestão de negociação — avaliar pelo preço pedido.</div>'

    return f"""<div class="card" data-id="{iid}">
  <div class="ph">{imgs}{setas}<span class="badge {badge_cls}">{badge}</span></div>
  <div class="body">
    <a class="t" href="{url}" target="_blank" rel="noreferrer">{titulo}</a>
    <div class="meta">{tam} · <b>{preco}</b></div>
    {neg_html}
    <div class="vote">
      <button class="v gostei" data-r="gostei">👍 Gostei</button>
      <button class="v nao" data-r="nao_gostei">👎 Não</button>
      <button class="v disc" data-r="discordo">⚠️ Discordo</button>
    </div>
    <textarea class="obs" rows="2" placeholder="Comentário (opcional): o que achou? até quanto pagaria?"></textarea>
    <div class="status"></div>
  </div>
</div>"""


def main() -> None:
    cand = _candidatos()
    cards = "\n".join(_card(it) for it in cand)
    n_comp = sum(1 for x in cand if (x.get("score") or {}).get("decisao") == "compravel")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Sundek · Vote nos candidatos</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#0e0e12; color:#f5f5f7; padding:16px 12px 60px; }}
.wrap {{ max-width:760px; margin:0 auto; }}
h1 {{ font-size:20px; margin-bottom:4px; }}
.sub {{ color:#b8b8c0; font-size:13px; margin-bottom:18px; }}
.grid {{ display:grid; grid-template-columns:1fr; gap:14px; }}
@media(min-width:640px) {{ .grid {{ grid-template-columns:1fr 1fr; }} }}
.card {{ background:#17171d; border:1px solid rgba(255,255,255,.08); border-radius:16px; overflow:hidden; }}
.card.voted {{ border-color:#00d9ff; }}
.ph {{ position:relative; width:100%; aspect-ratio:1; background:#0b0b0f; }}
.ph img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.ph img[hidden] {{ display:none; }}
.nav {{ position:absolute; top:50%; transform:translateY(-50%); width:38px; height:38px;
  border:none; border-radius:50%; background:rgba(0,0,0,.45); color:#fff; font-size:22px;
  cursor:pointer; display:flex; align-items:center; justify-content:center; }}
.nav.prev {{ left:8px; }} .nav.next {{ right:8px; }}
.count {{ position:absolute; top:8px; right:8px; background:rgba(0,0,0,.5); color:#fff;
  font-size:11px; padding:2px 7px; border-radius:99px; }}
.badge {{ position:absolute; top:8px; left:8px; font-size:12px; padding:3px 9px; border-radius:99px; font-weight:600; }}
.badge.comp {{ background:#00ff88; color:#07140a; }}
.badge.barg {{ background:#ffaa00; color:#1c1100; }}
.body {{ padding:12px; display:flex; flex-direction:column; gap:9px; }}
.t {{ color:#f5f5f7; text-decoration:none; font-size:14px; line-height:1.35; }}
.t:hover {{ text-decoration:underline; }}
.meta {{ color:#b8b8c0; font-size:13px; }} .meta b {{ color:#f5f5f7; }}
.neg {{ font-size:13px; line-height:1.45; padding:8px 10px; border-radius:10px; border:1px solid; }}
.neg.fechar {{ background:rgba(0,255,136,.1); color:#5dffb0; border-color:rgba(0,255,136,.25); }}
.neg.negociar {{ background:rgba(255,170,0,.1); color:#ffcc66; border-color:rgba(255,170,0,.25); }}
.neg.none {{ background:rgba(255,255,255,.04); color:#9a9aa6; border-color:rgba(255,255,255,.08); }}
.vote {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:2px; }}
.v {{ padding:9px 4px; border:1px solid rgba(255,255,255,.12); border-radius:10px;
  background:rgba(255,255,255,.04); color:#f5f5f7; font-size:12px; font-weight:600; cursor:pointer; }}
.v:active {{ transform:scale(.97); }}
.v.sel.gostei {{ background:#00ff88; color:#07140a; border-color:#00ff88; }}
.v.sel.nao {{ background:#ff4d6d; color:#fff; border-color:#ff4d6d; }}
.v.sel.disc {{ background:#ffaa00; color:#1c1100; border-color:#ffaa00; }}
.obs {{ width:100%; margin-top:2px; padding:9px 10px; border-radius:10px; resize:vertical;
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); color:#f5f5f7;
  font-size:14px; font-family:inherit; line-height:1.4; }}
.obs::placeholder {{ color:#7a7a86; }}
.obs:focus {{ outline:none; border-color:#00d9ff; }}
.status {{ font-size:11px; color:#00d9ff; min-height:14px; }}
</style></head><body>
<div class="wrap">
  <h1>Sundek · Candidatos a compra</h1>
  <div class="sub">{len(cand)} peças ({n_comp} compráveis · {len(cand) - n_comp} barganha).
    Veja o short e a sugestão de negociação, e vote 👍 / 👎 / ⚠️.</div>
  <div class="grid">{cards}</div>
</div>
<script>
const API="{API}", NS="{NS}";
// carrega votos já feitos
fetch(API+"/reactions").then(r=>r.json()).then(data=>{{
  document.querySelectorAll(".card").forEach(c=>{{
    const v=data[NS+c.dataset.id]; if(!v) return;
    if(v.reaction){{ const b=c.querySelector(`.v[data-r="${{v.reaction}}"]`);
      if(b){{ b.classList.add("sel"); c.classList.add("voted"); }} }}
    if(v.observacao){{ c.querySelector(".obs").value=v.observacao; }}
  }});
}}).catch(()=>{{}});

document.querySelectorAll(".card").forEach(card=>{{
  // carrossel
  const imgs=[...card.querySelectorAll(".ph img")], cnt=card.querySelector(".count");
  let idx=0;
  const show=i=>{{ idx=(i+imgs.length)%imgs.length; imgs.forEach((im,j)=>im.hidden=j!==idx);
    if(cnt) cnt.textContent=(idx+1)+"/"+imgs.length; }};
  if(imgs.length>1){{ show(0);
    card.querySelector(".prev").onclick=()=>show(idx-1);
    card.querySelector(".next").onclick=()=>show(idx+1);
    let x0=null; const ph=card.querySelector(".ph");
    ph.addEventListener("touchstart",e=>x0=e.touches[0].clientX,{{passive:true}});
    ph.addEventListener("touchend",e=>{{ if(x0==null)return; const dx=e.changedTouches[0].clientX-x0;
      if(Math.abs(dx)>35) show(idx+(dx<0?1:-1)); x0=null; }});
  }}
  // voto
  card.querySelectorAll(".v").forEach(btn=>{{
    btn.onclick=async()=>{{
      const sel=btn.classList.contains("sel");
      card.querySelectorAll(".v").forEach(b=>b.classList.remove("sel"));
      const r=sel?null:btn.dataset.r;
      if(!sel) btn.classList.add("sel");
      card.classList.toggle("voted",!sel);
      const st=card.querySelector(".status"); st.textContent="salvando…";
      try{{ await fetch(API+"/reactions",{{method:"POST",headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{id:NS+card.dataset.id,reaction:r}})}}); st.textContent=sel?"removido":"salvo ✓"; }}
      catch(e){{ st.textContent="erro"; st.style.color="#ff4d6d"; }}
      setTimeout(()=>st.textContent="",2000);
    }};
  }});
  // comentário — salva ao sair do campo
  const obs=card.querySelector(".obs");
  obs.addEventListener("blur",async()=>{{
    const st=card.querySelector(".status"); st.textContent="salvando…"; st.style.color="#00d9ff";
    try{{ await fetch(API+"/reactions",{{method:"POST",headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{id:NS+card.dataset.id,observacao:obs.value}})}}); st.textContent="comentário salvo ✓"; }}
    catch(e){{ st.textContent="erro"; st.style.color="#ff4d6d"; }}
    setTimeout(()=>st.textContent="",2000);
  }});
}});
</script>
</body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"OK -> {OUT}  ({len(cand)} candidatos: {n_comp} compráveis, {len(cand) - n_comp} barganha)")


if __name__ == "__main__":
    main()
