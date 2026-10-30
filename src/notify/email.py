"""Monta o email-resumo (HTML) e envia por SMTP (Gmail App Password).

Variáveis de ambiente (secrets do GitHub Actions):
  SMTP_USER  remetente (ex: scraping.didier@gmail.com)
  SMTP_PASS  App Password de 16 caracteres (sem espaços)
  NOTIFY_TO  destinatário(s), separados por vírgula
  SMTP_HOST  (opcional) padrão smtp.gmail.com
  SMTP_PORT  (opcional) padrão 587 (STARTTLS)
"""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage

SITE_VOTACAO = "https://votacao-two.vercel.app/"


# Paleta do app (votacao/app/globals.css): algodão, nanquim, kraft e as cores de sinal.
_C = {
    "canvas": "#f2f3f1", "surface": "#ffffff", "line": "#dcdfd8", "ink": "#1b2433",
    "ink2": "#4b5462", "ink3": "#7b828c", "kraft": "#dcc596", "kraft_ink": "#3d2f14",
    "buy": "#13784a", "buy_soft": "#e2f1e9", "deal": "#a65f00", "deal_soft": "#fbefd9",
    "urgent": "#c4302b", "urgent_soft": "#fbe7e5", "gold": "#8a6400", "gold_soft": "#fff1c4",
}
_FONTE = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def _selo(it: dict) -> tuple[str, str, str]:
    """(texto, fundo, cor do texto) da etiqueta — premiado > urgente > comprável > barganha."""
    p = it.get("premiado") or {}
    nota = it.get("score")
    if p.get("urgente"):
        return "Premiado, compra urgente", _C["urgent"], "#ffffff"
    if p.get("modelo"):
        return "Short premiado", _C["gold_soft"], _C["gold"]
    if (it.get("negociacao") or {}).get("comprar_ja"):
        return "Compre já", _C["urgent"], "#ffffff"
    if it.get("decisao") == "compravel":
        return f"Comprável {nota}" if nota is not None else "Comprável", _C["kraft"], _C["kraft_ink"]
    return f"Barganha {nota}" if nota is not None else "Barganha", "#ecdcbc", "#5a4214"


def _eur(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 0.005 else f"{v:.2f}".replace(".", ",")


def _preco_html(it: dict) -> str:
    """"€13" em destaque + "Total ≈ €19,60 (+€1,35 de taxa, frete desde €5,25)" — igual ao card
    do app; a oferta sugerida é sobre os €13."""
    base = it.get("preco_base")
    if not base:
        return (f'<span style="font-size:24px;font-weight:700;color:{_C["ink"]}">'
                f'{html.escape(it.get("preco") or "")}</span>')
    extras = []
    if it.get("taxa"):
        extras.append(f"+€{_eur(it['taxa'])} de taxa")
    if it.get("frete"):
        extras.append(f"frete desde €{_eur(it['frete'])}")
    total = base + (it.get("taxa") or 0) + (it.get("frete") or 0)
    sub = ""
    if extras:
        sub = (f'<div style="font-size:12px;color:{_C["ink3"]};margin-top:2px">'
               f'Total ≈ €{_eur(total)} ({", ".join(extras)})</div>')
    return (f'<div style="font-size:26px;line-height:1;font-weight:700;color:{_C["ink"]};'
            f'letter-spacing:-0.5px">€{_eur(base)}</div>{sub}')


def assunto_premiado(itens: list[dict]) -> str | None:
    """Assunto quando há short premiado entre os novos (o 1º da lista, que já vem ordenado
    com o premiado urgente na frente). None se não há premiado."""
    prem = [it for it in itens if (it.get("premiado") or {}).get("modelo")]
    if not prem:
        return None
    it = prem[0]
    preco = f"€{_eur(it['preco_base'])}" if it.get("preco_base") else (it.get("preco") or "")
    tam = it.get("tamanho") or "?"
    if (it.get("premiado") or {}).get("urgente"):
        assunto = f"🚨 Compra urgente: short premiado por {preco}, tam {tam}"
    else:
        assunto = f"⭐ Short premiado à venda por {preco}, tam {tam}"
    if len(itens) > 1:
        assunto += f" (+{len(itens) - 1} oferta{'s' if len(itens) > 2 else ''})"
    return assunto


def assunto_comum(itens: list[dict], marca_label: str) -> str:
    """"3 ofertas novas de Sundek, a partir de €9" (sem premiado)."""
    n = len(itens)
    precos = [it["preco_base"] for it in itens if it.get("preco_base")]
    a_partir = f", a partir de €{_eur(min(precos))}" if precos else ""
    return f"{n} {'oferta nova' if n == 1 else 'ofertas novas'} de {marca_label}{a_partir}"


def _botao(url: str, texto: str, escuro: bool = True) -> str:
    if escuro:
        estilo = f"background:{_C['ink']};color:#ffffff;border:1px solid {_C['ink']}"
    else:
        estilo = f"background:#ffffff;color:{_C['ink']};border:1px solid {_C['line']}"
    return (f'<a href="{url}" style="display:inline-block;{estilo};font-size:14px;font-weight:600;'
            f'text-decoration:none;padding:9px 14px;border-radius:8px;margin:0 8px 6px 0">{texto}</a>')


def _card_html(it: dict) -> str:
    texto_selo, fundo_selo, cor_selo = _selo(it)
    foto = (it.get("fotos") or [None])[0] or ""
    neg = it.get("negociacao") or {}
    msg_neg = html.escape((neg.get("msg") or "").lstrip("💰🗨️ ").strip())
    tam = html.escape(it.get("tamanho") or "?")
    estado = html.escape(it.get("estado") or "")
    titulo = html.escape(it.get("titulo") or "(sem título)")
    url = it.get("url") or SITE_VOTACAO
    # "Ver no app" abre o app já no card deste short (?id= rola até ele e destaca).
    url_app = f"{SITE_VOTACAO}?id={it.get('id')}" if it.get("id") else SITE_VOTACAO

    prem = it.get("premiado") or {}
    borda = (f"2px solid {_C['urgent'] if prem.get('urgente') else _C['gold']}"
             if prem.get("modelo") else f"1px solid {_C['line']}")
    linha_prem = ""
    if prem.get("modelo"):
        cor = _C["urgent"] if prem.get("urgente") else _C["gold"]
        fundo = _C["urgent_soft"] if prem.get("urgente") else _C["gold_soft"]
        linha_prem = (f'<div style="font-size:13px;color:{cor};background:{fundo};border-radius:8px;'
                      f'padding:8px 10px;margin:10px 0 0">É um dos seus 3 favoritos: '
                      f'{html.escape(prem.get("nome") or "")}.</div>')

    conferido = "".join(
        f'<div style="font-size:13px;color:{_C["ink2"]};margin:2px 0">'
        f'<span style="color:{_C["buy"]};font-weight:700">✓</span>&nbsp; '
        f'{html.escape((d[:1].upper() + d[1:]).replace("_", " "))}</div>'
        for d in (it.get("destaques") or []))
    neg_html = ""
    if msg_neg:
        fechar = neg.get("modo") == "fechar"
        neg_html = (f'<div style="font-size:13px;line-height:1.4;color:{"#0d5c38" if fechar else "#7a4600"};'
                    f'background:{_C["buy_soft"] if fechar else _C["deal_soft"]};border-radius:8px;'
                    f'padding:9px 11px;margin:10px 0 0">{msg_neg}</div>')

    img = (f'<img src="{foto}" width="132" height="132" '
           f'style="border-radius:8px;object-fit:cover;display:block;background:{_C["canvas"]}" alt="">'
           ) if foto else ""

    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border:{borda};
           border-radius:12px;margin:0 0 14px;background:{_C['surface']};border-collapse:separate">
      <tr>
        <td style="padding:14px;vertical-align:top;width:132px">{img}</td>
        <td style="padding:14px 14px 14px 0;vertical-align:top;font-family:{_FONTE}">
          <span style="display:inline-block;background:{fundo_selo};color:{cor_selo};font-size:12px;
                font-weight:700;padding:4px 9px;border-radius:4px 6px 6px 4px">{texto_selo}</span>
          <div style="font-size:15px;font-weight:600;color:{_C['ink']};margin:8px 0 8px;line-height:1.3">{titulo}</div>
          {_preco_html(it)}
          <div style="font-size:13px;color:{_C['ink2']};margin:8px 0 6px">
            Tamanho <b style="color:{_C['ink']}">{tam}</b>{f', {estado}' if estado else ''}
          </div>
          {conferido}
          {linha_prem}
          {neg_html}
          <div style="margin-top:12px">{_botao(url, "Abrir no Vinted")}{_botao(url_app, "Ver no app", escuro=False)}</div>
        </td>
      </tr>
    </table>"""


def corpo_html(marca_label: str, itens: list[dict]) -> str:
    n = len(itens)
    cards = "".join(_card_html(it) for it in itens)
    prem = [it for it in itens if (it.get("premiado") or {}).get("modelo")]
    if any((it.get("premiado") or {}).get("urgente") for it in prem):
        titulo = "Compra urgente: um dos seus shorts premiados está à venda com preço bom"
    elif prem:
        titulo = "Um dos seus shorts premiados está à venda"
    else:
        titulo = f"{n} {'oferta nova' if n == 1 else 'ofertas novas'} de {html.escape(marca_label)}"
    from datetime import datetime, timedelta, timezone
    agora = datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M")
    return f"""\
<div style="background:{_C['canvas']};padding:20px 12px;font-family:{_FONTE}">
<div style="max-width:620px;margin:0 auto">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 18px">
    <tr>
      <td style="font-size:22px;font-weight:800;color:{_C['ink']};letter-spacing:-0.5px">
        <span style="display:inline-block;width:14px;height:18px;background:{_C['kraft']};border:1.5px solid {_C['ink']};
              border-radius:2px 4px 4px 2px;vertical-align:-2px;margin-right:6px"></span>didi
      </td>
      <td align="right" style="font-size:12px;color:{_C['ink3']}">Radar de revenda<br>{html.escape(marca_label)} no Vinted</td>
    </tr>
  </table>
  <h1 style="font-size:21px;line-height:1.3;color:{_C['ink']};margin:0 0 6px;font-weight:700">{titulo}</h1>
  <p style="font-size:14px;color:{_C['ink2']};margin:0 0 18px">
    Encontradas às {agora}. Os anúncios bons costumam sumir em poucas horas.
  </p>
  {cards}
  <p style="font-size:12px;line-height:1.5;color:{_C['ink3']};margin:18px 0 0">
    O Didi confere cor, listra, bolso, elástico, tamanho e preço de cada anúncio e só avisa o que passa
    nas suas regras. <a href="{SITE_VOTACAO}" style="color:{_C['ink2']}">Ver todas as ofertas</a>
  </p>
</div>
</div>"""


def enviar(assunto: str, html: str) -> None:
    """Envia o email por SMTP. Lança exceção se a config estiver incompleta ou o
    envio falhar — assim falha visível no log e reenvía na próxima rodada."""
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    destinatarios = [e.strip() for e in os.environ.get("NOTIFY_TO", "").split(",") if e.strip()]
    if not (user and pwd and destinatarios):
        raise RuntimeError("SMTP_USER / SMTP_PASS / NOTIFY_TO não configurados.")

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = user
    msg["To"] = ", ".join(destinatarios)
    msg.set_content("Seu cliente de email não renderiza HTML. Abra: " + SITE_VOTACAO)
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls(context=ctx)
        s.login(user, pwd)
        s.send_message(msg)
