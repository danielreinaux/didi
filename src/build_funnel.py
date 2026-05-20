"""Gera data/funil.html — visão hierárquica das camadas de exclusão.

Hierarquia:
  RAIZ
  ├─ Não é o produto certo
  │  ├─ Não é short
  │  └─ Não é Sundek
  ├─ É Sundek + short, mas com problema visual
  │  ├─ Estampado
  │  ├─ Logo grande
  │  ├─ Desbotado
  │  ├─ Brilhoso
  │  ├─ Bicolor
  │  └─ Listra na frente
  ├─ Cor sem apelo de mercado
  ├─ Tamanho fora do range
  │  ├─ XS
  │  ├─ XXL
  │  └─ Numérico fora 31-34
  ├─ Coleção antiga (não vende)
  │  ├─ Bolso só com logo (sem nome SUNDEK)
  │  └─ Cordão fino
  ├─ Estrutura errada
  │  ├─ Bolso frontal
  │  ├─ Sem bolso traseiro
  │  ├─ Sem listra Sundek
  │  └─ Listra única (piping, não é Sundek)
  ├─ Fechamento ruim
  │  ├─ Botão
  │  └─ Velcro
  └─ Excluídos manualmente
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


# Mapeia código de exclusão → (grupo pai, label legível, ordem)
GRUPOS = {
    "Não é o produto certo": [
        ("nao_short", "Não é short (camiseta, polo, sunga, etc.)"),
        ("nao_sundek", "Não é da marca Sundek"),
    ],
    "Estilo visual excludente": [
        ("estampado", "Estampado (floral, listrado, geométrico)"),
        ("logo_grande", "Logo SUNDEK gigante na perna"),
        ("desbotado", "Tecido desbotado / lavado"),
        ("tecido_brilhoso", "Tecido brilhoso / acetinado"),
        ("bicolor", "Painel bicolor"),
        ("listra_na_frente", "Listra na frente do corpo"),
    ],
    "Cor sem apelo de mercado": [
        ("cor_ruim", "Cor ruim (neon, berrante, sem saída comercial)"),
    ],
    "Tamanho fora do range": [
        ("tamanho_XS", "XS"),
        ("tamanho_XXL", "XXL"),
        ("tamanho_numerico_26", "Numérico 26"),
        ("tamanho_numerico_27", "Numérico 27"),
        ("tamanho_numerico_28", "Numérico 28"),
        ("tamanho_numerico_29", "Numérico 29"),
        ("tamanho_numerico_30", "Numérico 30"),
        ("tamanho_numerico_36", "Numérico 36"),
        ("tamanho_numerico_38", "Numérico 38"),
    ],
    "Coleção antiga (não vende)": [
        ("bolso_so_logo_colecao_antiga", "Bolso só com logo (sem palavra SUNDEK no patch)"),
    ],
    "Estrutura errada": [
        ("bolso_frontal", "Bolso frontal/cargo (estilo boardshort)"),
        ("sem_bolso_traseiro", "Sem bolso traseiro"),
        ("sem_listra_sundek", "Sem listra Sundek autêntica"),
        ("piping_nao_e_listra_sundek", "Piping de costura (não é listra Sundek real)"),
    ],
    "Fechamento ruim": [
        ("fechamento_botao", "Botão no fly"),
        ("fechamento_velcro", "Velcro"),
    ],
}


def carregar() -> list:
    return json.loads((DATA / "coleta-classificada.json").read_text())


def main() -> None:
    itens = carregar()

    # Agrupa itens por código de exclusão
    por_codigo: dict[str, list[dict]] = {}
    excluidos_manuais: list[dict] = []
    for it in itens:
        if it.get("manual_exclusao"):
            excluidos_manuais.append(it)
            continue
        s = it.get("score") or {}
        motivo = s.get("motivo_exclusao", "")
        if not motivo:
            continue
        for codigo in motivo.split(", "):
            por_codigo.setdefault(codigo.strip(), []).append(it)

    total_descartados = sum(1 for it in itens
                            if (it.get("score") or {}).get("decisao") == "descartado"
                            or it.get("manual_exclusao"))

    def render_item(it: dict) -> str:
        foto = (it.get("fotos") or [""])[0]
        titulo = escape(it.get("titulo") or "")[:60]
        preco = escape(it.get("preco") or "?")
        tamanho = escape(it.get("tamanho") or "?")
        cor_data = it.get("cor") or {}
        if isinstance(cor_data, dict):
            cor = escape(cor_data.get("cor_principal") or "?")
        else:
            cor = "?"
        url = escape(it.get("url") or "#")
        return f"""<div class="item">
  <img src="{foto}" loading="lazy" alt="">
  <div class="item-body">
    <a href="{url}" target="_blank" class="title">{titulo}</a>
    <div class="meta">{preco} · {tamanho} · {cor}</div>
  </div>
</div>"""

    # Calcula contagens reais (itens únicos, dedupe se item tem múltiplos motivos)
    total_por_grupo: dict[str, int] = {}
    ids_por_grupo: dict[str, set] = {}
    for grupo, codigos in GRUPOS.items():
        ids = set()
        for cod, _label in codigos:
            for it in por_codigo.get(cod, []):
                ids.add(it.get("id"))
        ids_por_grupo[grupo] = ids
        total_por_grupo[grupo] = len(ids)

    total_manuais = len(excluidos_manuais)

    grupos_html_parts = []
    for grupo, codigos in GRUPOS.items():
        total_g = total_por_grupo[grupo]
        if total_g == 0:
            continue
        sub_parts = []
        for cod, label in codigos:
            its = por_codigo.get(cod, [])
            if not its:
                continue
            items_html = "\n".join(render_item(it) for it in its[:200])
            mais = "" if len(its) <= 200 else f'<div class="more">+ {len(its)-200} itens (limitado a 200)</div>'
            sub_parts.append(f"""<details class="sub">
  <summary><span class="cnt-sub">{len(its)}</span> {escape(label)} <code>{cod}</code></summary>
  <div class="items-grid">{items_html}</div>
  {mais}
</details>""")
        grupos_html_parts.append(f"""<details class="grupo" open>
  <summary><span class="cnt-grupo">{total_g}</span> {escape(grupo)}</summary>
  <div class="subs">
  {''.join(sub_parts)}
  </div>
</details>""")

    if excluidos_manuais:
        items_html = "\n".join(render_item(it) for it in excluidos_manuais)
        grupos_html_parts.append(f"""<details class="grupo">
  <summary><span class="cnt-grupo">{total_manuais}</span> Excluídos manualmente</summary>
  <div class="subs">
    <details class="sub">
      <summary><span class="cnt-sub">{total_manuais}</span> Decisão humana (após inspeção)</summary>
      <div class="items-grid">{items_html}</div>
    </details>
  </div>
</details>""")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Didi · Funil de exclusões</title>
<style>
:root {{
  --bg: #f7f7f5; --surface: #fff; --ink: #111; --soft: #555;
  --mute: #999; --border: #e0e0e0; --accent: #b91c1c;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.5;
  padding: 24px 16px 60px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 6px; }}
.hero-stats {{
  display: flex; gap: 16px; margin: 16px 0 28px;
  font-size: 14px; color: var(--soft);
}}
.hero-stats span {{ background: #fff; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border); }}
.hero-stats b {{ color: var(--ink); }}

details {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; margin-bottom: 10px; overflow: hidden;
}}
details.grupo {{ background: var(--surface); }}
details.sub {{ background: #fafafa; border: 1px solid #ececec; margin: 8px; }}

summary {{
  cursor: pointer; padding: 14px 16px; font-weight: 600;
  list-style: none; user-select: none;
  display: flex; align-items: center; gap: 10px;
  font-size: 15px;
}}
summary::-webkit-details-marker {{ display: none; }}
summary::before {{
  content: "▸"; font-size: 13px; color: var(--mute);
  transition: transform .15s;
}}
details[open] > summary::before {{ transform: rotate(90deg); }}
details.sub summary {{ padding: 10px 14px; font-weight: 500; font-size: 13px; }}

.cnt-grupo, .cnt-sub {{
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 38px; padding: 2px 8px;
  background: var(--accent); color: #fff;
  border-radius: 99px; font-size: 13px; font-weight: 700;
}}
.cnt-sub {{ background: #6b7280; font-size: 12px; min-width: 32px; }}

code {{
  background: #f0f0ee; padding: 1px 6px; border-radius: 4px;
  font-size: 11px; color: var(--soft);
  font-family: ui-monospace, "SF Mono", monospace;
}}

.items-grid {{
  display: grid; gap: 10px; padding: 4px 14px 14px;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}}
.item {{
  background: #fff; border: 1px solid var(--border); border-radius: 8px;
  overflow: hidden; display: flex; flex-direction: column;
}}
.item img {{ width: 100%; aspect-ratio: 1/1; object-fit: cover; background: #eee; }}
.item-body {{ padding: 8px 10px; font-size: 12px; }}
.item .title {{
  display: block; color: var(--ink); text-decoration: none;
  font-weight: 500; line-height: 1.3; margin-bottom: 4px;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}}
.item .title:hover {{ color: var(--accent); text-decoration: underline; }}
.item .meta {{ color: var(--soft); font-size: 11px; }}
.more {{ padding: 8px 14px; color: var(--mute); font-size: 12px; }}
</style>
</head>
<body>
<div class="container">

<h1>Funil de exclusões — por que cada item caiu fora</h1>
<div class="hero-stats">
  <span>Total no scrape: <b>{len(itens)}</b></span>
  <span>Descartados: <b>{total_descartados}</b></span>
  <span>Compráveis: <b>{sum(1 for it in itens if (it.get("score") or {{}}).get("decisao")=="compravel" and not it.get("manual_exclusao"))}</b></span>
  <span>Barganha: <b>{sum(1 for it in itens if (it.get("score") or {{}}).get("decisao")=="medio" and not it.get("manual_exclusao"))}</b></span>
</div>

{''.join(grupos_html_parts)}

</div>
</body>
</html>"""

    out = DATA / "funil.html"
    out.write_text(html)
    print(f"OK → {out}")
    print(f"Abra com: open {out}")


if __name__ == "__main__":
    main()
