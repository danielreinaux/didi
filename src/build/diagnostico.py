"""Gera data/diagnostico.html — visão item-a-item com TODAS as métricas dos
classificadores explicadas, para auditar como cada classificador está indo.

Uso: python -m src.build_diagnostico
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAPSHOT = Path("/tmp/historico_snapshot.json")


def _badge(label: str, valor, bom=None) -> str:
    """Renderiza uma métrica. bom: True=verde, False=vermelho, None=neutro."""
    cls = "n"
    if bom is True:
        cls = "g"
    elif bom is False:
        cls = "r"
    return f'<span class="m m-{cls}"><b>{escape(label)}</b> {escape(str(valor))}</span>'


def card(it: dict, novo: bool) -> str:
    cl = it.get("classificacao") or {}
    marca = it.get("marca_check") or {}
    cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
    el = it.get("elastico") or {}
    etq = it.get("etiqueta") or {}
    sc = it.get("score") or {}

    fotos = (it.get("fotos") or [])[:8]
    foto = fotos[0] if fotos else ""
    outras = "".join(f'<img src="{u}" loading="lazy">' for u in fotos[1:])

    titulo = escape(it.get("titulo") or "")[:60]
    preco = escape(it.get("preco") or "?")
    tam = escape(it.get("tamanho") or "?")
    url = escape(it.get("url") or "#")
    tipo = cl.get("tipo") or "?"

    decisao = sc.get("decisao", "?")
    dec_cls = {"compravel": "g", "medio": "n", "descartado": "r"}.get(decisao, "n")

    # Métricas
    metricas = []
    # Marca
    metricas.append(_badge("Sundek?", marca.get("e_sundek", "?"), marca.get("e_sundek") == "sim"))
    metricas.append(_badge("é short?", marca.get("e_short", "?"), marca.get("e_short") == "sim"))
    # Tipo
    metricas.append(_badge("tipo", tipo, tipo == "liso"))
    if cl.get("bicolor"):
        metricas.append(_badge("bicolor", "sim", False))
    if cl.get("tecido_brilhoso"):
        metricas.append(_badge("brilhoso", "sim", False))
    if cl.get("tem_bolso_frontal"):
        metricas.append(_badge("bolso frontal", "sim", False))
    if cl.get("listra_na_frente"):
        metricas.append(_badge("listra na frente", "sim", False))
    # Cor
    if cor:
        tier = cor.get("tier_final") or cor.get("tier") or "?"
        metricas.append(_badge("cor", cor.get("cor_principal", "?"), None))
        metricas.append(_badge("tier", tier, tier not in ("ruim", "ok")))
    # Listra
    if cl.get("tem_listra_lateral_sundek") is not None:
        tl = cl.get("tem_listra_lateral_sundek")
        metricas.append(_badge("listra Sundek", "sim" if tl else "não", tl))
    if cl.get("cores_listras"):
        metricas.append(_badge("cores listra", ", ".join(cl["cores_listras"]), None))
    if cl.get("e_piping"):
        metricas.append(_badge("piping", "sim", False))
    # Bolso
    tb = cl.get("tem_bolso_traseiro")
    if tb is not None:
        metricas.append(_badge("bolso traseiro", "sim" if tb else "não", tb))
    tn = cl.get("bolso_traseiro_tem_nome")
    if tn is not None:
        metricas.append(_badge("nome SUNDEK no bolso", "sim" if tn else "não", tn))
    # Elástico
    if el.get("tem_elastico") is not None:
        te = el.get("tem_elastico")
        metricas.append(_badge("elástico", "sim" if te else "não", te))
    if el.get("tipo_fechamento"):
        tf = el.get("tipo_fechamento")
        metricas.append(_badge("fechamento", tf, tf not in ("botao", "velcro")))
    # Etiqueta
    if etq.get("tem_etiqueta") is not None:
        metricas.append(_badge("etiqueta (hang tag)", "sim" if etq.get("tem_etiqueta") else "não",
                               True if etq.get("tem_etiqueta") else None))

    metricas_html = "".join(metricas)

    # Evidências (texto livre dos classificadores)
    evids = []
    if marca.get("evidencia"):
        evids.append(f"<b>marca:</b> {escape(marca['evidencia'])}")
    if cl.get("listra_evidencia"):
        evids.append(f"<b>listra:</b> {escape(cl['listra_evidencia'])}")
    if cl.get("bolso_evidencia"):
        evids.append(f"<b>bolso:</b> {escape(cl['bolso_evidencia'])}")
    if el.get("evidencia"):
        evids.append(f"<b>elástico:</b> {escape(el['evidencia'])}")
    if etq.get("evidencia"):
        evids.append(f"<b>etiqueta:</b> {escape(etq['evidencia'])}")
    evids_html = "".join(f"<div class='ev'>{e}</div>" for e in evids)

    motivo = sc.get("motivo_exclusao") or sc.get("motivo") or ""
    novo_badge = '<span class="novo">NOVO</span>' if novo else ""

    return f"""<article class="card">
  <div class="thumbs"><img src="{foto}" class="main" loading="lazy">{outras}</div>
  <div class="body">
    <div class="head">
      {novo_badge}
      <a href="{url}" target="_blank" class="t">{titulo}</a>
    </div>
    <div class="sub">{preco} · tam {tam}</div>
    <div class="decisao d-{dec_cls}">{escape(decisao.upper())} · {sc.get('score',0)}pts{' · ' + escape(motivo) if motivo else ''}</div>
    <div class="metricas">{metricas_html}</div>
    {f'<div class="evids">{evids_html}</div>' if evids_html else ''}
  </div>
</article>"""


def _classificou_ok(it: dict) -> bool:
    """True se o item foi 100% classificado, sem erro em nenhuma etapa."""
    cl = it.get("classificacao") or {}
    if cl.get("tipo") in (None, "erro"):
        return False
    mc = it.get("marca_check") or {}
    if "erro" in str(mc.get("evidencia", "")):
        return False
    return True


def main() -> None:
    todos = json.loads((DATA / "coleta-classificada.json").read_text())
    itens = [it for it in todos if _classificou_ok(it)]

    ids_antigos = set()
    if SNAPSHOT.exists():
        try:
            ids_antigos = set(json.loads(SNAPSHOT.read_text()))
        except Exception:
            pass

    def is_novo(it):
        return str(it.get("id")) not in ids_antigos if ids_antigos else False

    # Novos primeiro, depois resto
    itens_ord = sorted(itens, key=lambda it: (0 if is_novo(it) else 1))
    n_novos = sum(1 for it in itens if is_novo(it))

    cards = "\n".join(card(it, is_novo(it)) for it in itens_ord)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Diagnóstico dos classificadores</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#f2f2f0; color:#18181b; padding:20px 14px 60px; }}
.container {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.sub-h {{ color:#666; font-size:13px; margin-bottom:20px; }}
.card {{ display:flex; gap:14px; background:#fff; border:1px solid #e0e0e0;
  border-radius:10px; padding:12px; margin-bottom:12px; }}
.thumbs {{ display:flex; flex-wrap:wrap; gap:4px; width:300px; flex-shrink:0; align-content:flex-start; }}
.thumbs img {{ width:70px; height:70px; object-fit:cover; border-radius:5px; background:#eee; }}
.thumbs img.main {{ width:144px; height:144px; }}
.body {{ flex:1; min-width:0; }}
.head {{ display:flex; align-items:center; gap:8px; }}
.novo {{ background:#2563eb; color:#fff; font-size:10px; font-weight:800;
  padding:2px 7px; border-radius:5px; }}
.t {{ font-weight:700; color:#18181b; text-decoration:none; font-size:15px; }}
.t:hover {{ text-decoration:underline; }}
.sub {{ color:#555; font-size:12px; margin:3px 0 6px; }}
.decisao {{ display:inline-block; font-size:12px; font-weight:700;
  padding:3px 9px; border-radius:6px; margin-bottom:8px; }}
.d-g {{ background:#dcfce7; color:#15803d; }}
.d-r {{ background:#fee2e2; color:#b91c1c; }}
.d-n {{ background:#fef9c3; color:#854d0e; }}
.metricas {{ display:flex; flex-wrap:wrap; gap:5px; }}
.m {{ font-size:11px; padding:3px 7px; border-radius:5px; background:#f0f0ee; }}
.m b {{ font-weight:700; }}
.m-g {{ background:#dcfce7; color:#15803d; }}
.m-r {{ background:#fee2e2; color:#b91c1c; }}
.m-n {{ background:#eef; color:#3730a3; }}
.evids {{ margin-top:8px; display:flex; flex-direction:column; gap:3px; }}
.ev {{ font-size:11px; color:#666; line-height:1.4; }}
.ev b {{ color:#333; }}
</style></head><body>
<div class="container">
<h1>Diagnóstico dos classificadores</h1>
<div class="sub-h">{len(itens)} itens · {n_novos} novos (badge azul). Cada card mostra a saída de TODOS os classificadores + as evidências.</div>
{cards}
</div></body></html>"""

    out = DATA / "diagnostico.html"
    out.write_text(html)
    print(f"OK -> {out}  ({len(itens)} itens, {n_novos} novos)")


if __name__ == "__main__":
    main()
