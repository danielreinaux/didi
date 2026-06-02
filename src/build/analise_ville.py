"""Gera data/analise-ville.html — auditoria da Vilebrequin (espelho do analise.py).

Agrupa por decisão (comprável/médio/descartado) e, nos descartados, por motivo.
Tags próprias da Ville: padrão (tartaruga), autenticidade, cor.
"""
import json
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

LEGENDAS = {
    # Padrões
    "padrao:tartaruga_grande": "Tartaruga GRANDE dominando o tecido — o foco da marca, comprável.",
    "padrao:tartaruga_pequena": "Tartarugas pequenas/mini — exceção, só com cor neutra + preço bom.",
    "padrao:liso": "Cor sólida sem estampa — comprável só nas cores aceitas e preço bom.",
    "padrao:outro": "Outro padrão (peixe, coral, âncora, estrela, etc.) — cliente não compra.",
    "padrao:indefinido": "Foto insuficiente pra dizer o padrão — vai pra análise manual.",
    # Autenticidade
    "auth:original": "Padrão continua dentro do bolso traseiro — original.",
    "auth:falso": "Bolso liso/cortado — padrão interrompido — falso. Descarta.",
    "auth:suspeito": "Bolso ambíguo — trava em médio até confirmar.",
    "auth:sem_foto_bolso": "Sem foto do bolso — possível compra, com flag de verificar.",
    "auth:indefinido": "Não dá pra avaliar o bolso (ex: liso) — possível compra, com flag.",
    # Motivos de exclusão
    "padrao_outro_nao_compra": "Padrão não é tartaruga nem liso (peixe/coral/âncora/etc.) — cliente não compra.",
    "autenticidade_falsa": "Bolso traseiro sem o padrão — peça falsa.",
    "desbotado": "Tecido com aparência lavada/envelhecida.",
    "tamanho_invalido": "Tamanho fora de S/M/L/XL (XS, XXL, numérico, talla única).",
    "cor_liso_fora_whitelist": "Liso numa cor que o cliente não compra (só preto/branco/navy/cinza/musgo/vermelho).",
    "nao_ville": "Título não bate com Vilebrequin (prefilter).",
    "nao_vilebrequin": "Marca diferente identificada pela foto.",
    "nao_short": "Não é short de banho (camiseta, calça, sunga, infantil, etc.).",
    "fora das faixas de compra": "Padrão/cor/preço não se encaixam em nenhuma regra de compra.",
}

_PTS_LABEL = {"padrao": "padrão", "cor": "cor", "tamanho": "tam",
              "etiqueta": "etiqueta", "autenticidade": "autent.", "preco": "preço"}


def _explicacao_score(s: dict) -> str:
    bd = s.get("breakdown") or {}
    if not bd:
        return ""
    partes = []
    for k in ("padrao", "cor", "tamanho", "etiqueta", "autenticidade", "preco"):
        if k in bd:
            v = bd[k]
            partes.append(f"{_PTS_LABEL.get(k, k)} {'+' if v >= 0 else ''}{v}")
    linha = " · ".join(partes)
    teto = s.get("teto")
    teto_txt = f" · teto €{teto}" if teto else ""
    return f'<div class="bd">score <b>{s.get("score", 0)}</b>{teto_txt}: {linha}</div>'


def main() -> None:
    inp = DATA / "coleta-ville-classificada.json"
    if not inp.exists():
        print("coleta-ville-classificada.json não encontrado.")
        return
    itens = json.loads(inp.read_text(encoding="utf-8"))
    total_acervo = len(itens)
    itens = [x for x in itens if x.get("status") not in ("vendido", "inativo")]

    dec = Counter((it.get("score") or {}).get("decisao", "?") for it in itens)
    compraveis = [it for it in itens if (it.get("score") or {}).get("decisao") == "compravel"]
    medios = [it for it in itens if (it.get("score") or {}).get("decisao") == "medio"]
    descartados = [it for it in itens if (it.get("score") or {}).get("decisao") == "descartado"]

    motivo_itens: dict[str, list] = {}
    for it in descartados:
        m = (it.get("score") or {}).get("motivo_exclusao", "") or (it.get("score") or {}).get("motivo", "") or "sem_motivo"
        for cod in str(m).split(", "):
            cod = cod.strip() or "sem_motivo"
            motivo_itens.setdefault(cod, []).append(it)

    def card(it: dict, mostrar_score=True) -> str:
        cl = it.get("classificacao") or {}
        tart = it.get("tartaruga") if isinstance(it.get("tartaruga"), dict) else {}
        cor = it.get("cor") if isinstance(it.get("cor"), dict) else {}
        auth = it.get("autenticidade") if isinstance(it.get("autenticidade"), dict) else {}
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
        cor_nome = cor.get("cor_principal") or tart.get("cor_principal")
        if cor_nome:
            tags.append(f'<span class="tag">{escape(cor_nome)}</span>')
        if tart.get("tartaruga_variedade"):
            tags.append(f'<span class="tag">{escape(tart["tartaruga_variedade"])}</span>')
        av = auth.get("autenticidade") or cl.get("autenticidade")
        if av == "original":
            tags.append('<span class="tag ok">original</span>')
        elif av == "falso":
            tags.append('<span class="tag x">FALSO</span>')
        elif av == "suspeito":
            tags.append('<span class="tag mid">suspeito</span>')
        elif av in ("sem_foto_bolso", "indefinido"):
            tags.append(f'<span class="tag mid">{escape(av)}</span>')
        if et.get("tem_etiqueta") is True:
            tags.append('<span class="tag ok">etiqueta</span>')
        for fl in (s.get("flags") or []):
            tags.append(f'<span class="tag mid">⚑ {escape(fl)}</span>')

        score_html = f'<span class="score">score <b>{s.get("score", 0)}</b></span>' if mostrar_score else ""

        ev = []
        if auth.get("evidencia"):
            ev.append(f"<b>bolso:</b> {escape(auth['evidencia'])}")
        if tart.get("justificativa"):
            ev.append(f"<b>padrão:</b> {escape(tart['justificativa'])}")
        evid = "<br>".join(ev)

        motivo = (s.get("motivo_exclusao") or "") or (s.get("motivo") or "")
        motivo_html = f'<div class="motivo">{escape(motivo)}</div>' if motivo else ''

        return f"""<div class="card">
  <div class="thumbs"><img src="{foto}" loading="lazy" class="main">{outras}</div>
  <div class="info">
    <a href="{url}" target="_blank" class="t">{titulo}</a>
    <div class="meta">{preco} · {tam} · {score_html}</div>
    <div class="tags">{''.join(tags)}</div>
    {motivo_html}
    {_explicacao_score(s)}
    <div class="evid">{evid}</div>
  </div>
</div>"""

    secoes = []
    if compraveis:
        cards = "\n".join(card(it) for it in sorted(compraveis, key=lambda x: -(x.get("score") or {}).get("score", 0)))
        secoes.append(f'<details class="grupo" open><summary><span class="cnt cnt-ok">✓ {len(compraveis)}</span> COMPRÁVEIS</summary><div class="lista">{cards}</div></details>')
    if medios:
        cards = "\n".join(card(it) for it in sorted(medios, key=lambda x: -(x.get("score") or {}).get("score", 0)))
        secoes.append(f'<details class="grupo" open><summary><span class="cnt cnt-mid">~ {len(medios)}</span> BARGANHA (médios)</summary><div class="lista">{cards}</div></details>')

    sub_motivos = []
    for cod, lista in sorted(motivo_itens.items(), key=lambda x: -len(x[1])):
        cards = "\n".join(card(it, mostrar_score=False) for it in lista[:80])
        mais = "" if len(lista) <= 80 else f'<div class="more">+ {len(lista) - 80} itens</div>'
        legenda = LEGENDAS.get(cod, "—")
        sub_motivos.append(f'<details class="sub"><summary><span class="cnt-sub">{len(lista)}</span> <code>{escape(cod)}</code> <span class="leg">— {escape(legenda)}</span></summary><div class="lista">{cards}</div>{mais}</details>')
    secoes.append(f'<details class="grupo"><summary><span class="cnt cnt-x">✗ {len(descartados)}</span> DESCARTADOS (por motivo)</summary><div class="subs">{"".join(sub_motivos)}</div></details>')

    leg_padroes = "".join(f'<tr><td><span class="tag tipo">{escape(k.replace("padrao:",""))}</span></td><td>{escape(v)}</td></tr>' for k, v in LEGENDAS.items() if k.startswith("padrao:"))
    leg_auth = "".join(f'<tr><td><code>{escape(k.replace("auth:",""))}</code></td><td>{escape(v)}</td></tr>' for k, v in LEGENDAS.items() if k.startswith("auth:"))
    leg_motivos = "".join(f'<tr><td><code>{escape(k)}</code></td><td>{escape(v)}</td></tr>' for k, v in LEGENDAS.items() if not k.startswith(("padrao:", "auth:")))

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Análise Vilebrequin</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f2f2f0;color:#18181b;padding:20px 14px 60px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:24px;margin-bottom:6px}} h2{{font-size:16px;margin:16px 0 8px;color:#52525b}}
.sub-h{{color:#666;font-size:13px;margin-bottom:18px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:20px}}
.stat{{background:#fff;border:1px solid #e4e4e7;border-radius:10px;padding:12px}}
.stat .v{{font-size:22px;font-weight:700}} .stat .l{{font-size:12px;color:#71717a;margin-top:4px}}
.stat.ok .v{{color:#15803d}} .stat.mid .v{{color:#a16207}} .stat.x .v{{color:#7f1d1d}}
.legenda{{background:#fff;border:1px solid #e4e4e7;border-radius:10px;padding:14px;margin-bottom:20px}}
.legenda summary{{cursor:pointer;font-weight:600;padding:4px 0}}
.legenda table{{width:100%;border-collapse:collapse;margin-top:10px}}
.legenda td{{padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:13px;vertical-align:top}}
.legenda td:first-child{{width:22%}}
.legenda code{{background:#f4f4f5;padding:1px 5px;border-radius:3px;font-size:11px;color:#52525b}}
details{{background:#fff;border:1px solid #e4e4e7;border-radius:10px;margin-bottom:12px;overflow:hidden}}
details.sub{{background:#fafafa;border:1px solid #ececec;margin:8px}}
summary{{cursor:pointer;padding:14px 16px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px;font-size:15px}}
summary::-webkit-details-marker{{display:none}}
summary::before{{content:"▸";color:#999;font-size:13px;transition:transform .15s}}
details[open]>summary::before{{transform:rotate(90deg)}}
details.sub summary{{padding:10px 14px;font-size:13px;font-weight:500}}
.cnt{{display:inline-flex;align-items:center;justify-content:center;min-width:32px;padding:3px 10px;border-radius:99px;font-size:13px;font-weight:700;background:#18181b;color:#fff}}
.cnt-ok{{background:#15803d}} .cnt-mid{{background:#a16207}} .cnt-x{{background:#7f1d1d}}
.cnt-sub{{background:#6b7280;color:#fff;font-size:12px;padding:2px 8px;border-radius:99px;min-width:28px;text-align:center}}
.leg{{color:#71717a;font-size:12px;font-weight:400}}
.lista{{padding:6px 14px 14px;display:flex;flex-direction:column;gap:10px}}
.card{{display:flex;gap:12px;background:#fafafa;border:1px solid #ececec;border-radius:8px;padding:10px}}
.thumbs{{display:flex;gap:4px;flex-wrap:wrap;width:280px;flex-shrink:0}}
.thumbs img{{width:64px;height:64px;object-fit:cover;border-radius:5px;background:#eee}}
.thumbs img.main{{width:132px;height:132px}}
.info{{flex:1;min-width:0}}
.t{{font-weight:600;color:#18181b;text-decoration:none;font-size:14px;line-height:1.3}}
.meta{{color:#444;font-size:13px;margin:4px 0}}
.score{{background:#f4f4f5;padding:1px 7px;border-radius:5px;font-size:11px;color:#52525b}}
.tags{{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0}}
.tag{{font-size:11px;padding:2px 7px;border-radius:99px;background:#eee;color:#333}}
.tag.tipo{{background:#dbeafe;color:#1e3a8a}} .tag.ok{{background:#dcfce7;color:#14532d}}
.tag.x{{background:#fee2e2;color:#7f1d1d}} .tag.mid{{background:#fef9c3;color:#713f12}}
.motivo{{color:#7f1d1d;font-size:12px;font-style:italic;margin-top:4px}}
.bd{{color:#3730a3;background:#eef2ff;border-radius:5px;padding:4px 8px;font-size:11px;margin-top:5px;line-height:1.5}}
.bd b{{color:#1e1b4b}}
.evid{{color:#666;font-size:11px;line-height:1.5;margin-top:6px;padding-top:6px;border-top:1px dashed #ddd}}
.evid b{{color:#333}} .more{{padding:8px 14px;color:#999;font-size:12px}}
</style></head><body>
<div class="container">
<h1>Didi · Análise Vilebrequin</h1>
<div class="sub-h">{len(itens)} itens à venda ({total_acervo} no acervo).</div>
<div class="stats">
  <div class="stat ok"><div class="v">{dec.get('compravel', 0)}</div><div class="l">Compráveis</div></div>
  <div class="stat mid"><div class="v">{dec.get('medio', 0)}</div><div class="l">Barganha (médios)</div></div>
  <div class="stat x"><div class="v">{dec.get('descartado', 0)}</div><div class="l">Descartados</div></div>
</div>
<details class="legenda">
  <summary>📖 Legenda — clique pra entender</summary>
  <h2>Padrão de estampa</h2><table>{leg_padroes}</table>
  <h2>Autenticidade (bolso traseiro)</h2><table>{leg_auth}</table>
  <h2>Motivos de exclusão</h2><table>{leg_motivos}</table>
</details>
<h2>Itens classificados</h2>
{''.join(secoes)}
</div></body></html>"""

    out = DATA / "analise-ville.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
