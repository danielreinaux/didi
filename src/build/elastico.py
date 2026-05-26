"""Gera data/elastico.html — itens agrupados por tipo de fechamento, para
auditar erros da detecção de elástico.
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

GRUPOS = [
    ("com_elastico", "Com elástico", lambda el: el.get("tem_elastico") is True),
    ("sem_elastico", "Sem elástico (cordão)", lambda el: el.get("tem_elastico") is False
        and el.get("tipo_fechamento") not in ("botao", "velcro")),
    ("botao", "Botão no fly", lambda el: el.get("tipo_fechamento") == "botao"),
    ("velcro", "Velcro", lambda el: el.get("tipo_fechamento") == "velcro"),
    ("indefinido", "Indefinido / sem dado", lambda el: el.get("tem_elastico") is None
        and el.get("tipo_fechamento") not in ("botao", "velcro")),
]


def main() -> None:
    itens = json.loads((DATA / "coleta-classificada.json").read_text())
    # Só itens que rodaram elástico (lisos aprovados)
    com_elastico = [it for it in itens if it.get("elastico") is not None]

    def card(it: dict) -> str:
        el = it.get("elastico") or {}
        fotos = (it.get("fotos") or [])[:8]
        foto = fotos[0] if fotos else ""
        outras = "".join(f'<img src="{u}" loading="lazy">' for u in fotos[1:])
        titulo = escape(it.get("titulo") or "")[:55]
        preco = escape(it.get("preco") or "?")
        tam = escape(it.get("tamanho") or "?")
        url = escape(it.get("url") or "#")
        evid = escape(el.get("evidencia") or "")
        fecho = escape(el.get("tipo_fechamento") or "?")
        return f"""<div class="card">
  <div class="thumbs"><img src="{foto}" loading="lazy" class="main">{outras}</div>
  <div class="info">
    <a href="{url}" target="_blank" class="t">{titulo}</a>
    <div class="meta">{preco} · {tam} · fecho: <b>{fecho}</b></div>
    <div class="evid">{evid}</div>
  </div>
</div>"""

    secoes = []
    for key, label, cond in GRUPOS:
        grupo = [it for it in com_elastico if cond(it.get("elastico") or {})]
        if not grupo:
            continue
        cards = "\n".join(card(it) for it in grupo)
        secoes.append(f"""<details class="grupo" open>
  <summary><span class="cnt">{len(grupo)}</span> {escape(label)}</summary>
  <div class="lista">{cards}</div>
</details>""")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Auditoria de elástico</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#f2f2f0; color:#18181b; padding:20px 14px 60px; }}
.container {{ max-width:1100px; margin:0 auto; }}
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
.t {{ font-weight:600; color:#18181b; text-decoration:none; font-size:14px; }}
.t:hover {{ text-decoration:underline; }}
.meta {{ color:#555; font-size:12px; margin:4px 0; }}
.evid {{ color:#777; font-size:12px; font-style:italic; line-height:1.4; }}
</style></head><body>
<div class="container">
<h1>Auditoria — detecção de elástico</h1>
<div class="sub">{len(com_elastico)} itens passaram pela verificação de fechamento. Clique para abrir o anúncio e conferir.</div>
{''.join(secoes)}
</div></body></html>"""

    out = DATA / "elastico.html"
    out.write_text(html)
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
