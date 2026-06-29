"""Monta o email-resumo (HTML) e envia por SMTP (Gmail App Password).

Variáveis de ambiente (secrets do GitHub Actions):
  SMTP_USER  remetente (ex: scraping.didier@gmail.com)
  SMTP_PASS  App Password de 16 caracteres (sem espaços)
  NOTIFY_TO  destinatário(s), separados por vírgula
  SMTP_HOST  (opcional) padrão smtp.gmail.com
  SMTP_PORT  (opcional) padrão 587 (STARTTLS)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

SITE_VOTACAO = "https://votacao-two.vercel.app/"


def _badge(it: dict) -> tuple[str, str]:
    """(texto, cor) do selo da oferta — urgente > comprável > barganha."""
    if (it.get("negociacao") or {}).get("comprar_ja"):
        return "⚡ COMPRE JÁ", "#ff3b6b"
    if it.get("decisao") == "compravel":
        return "🟢 COMPRÁVEL", "#00b050"
    return "🟠 BARGANHA", "#e08a00"


def _card_html(it: dict) -> str:
    texto_badge, cor_badge = _badge(it)
    foto = (it.get("fotos") or [None])[0] or ""
    neg = it.get("negociacao") or {}
    msg_neg = neg.get("msg") or ""
    destaques = " · ".join(it.get("destaques") or [])
    preco = it.get("preco") or ""
    tam = it.get("tamanho") or "?"
    cor = it.get("cor_ia") or ""
    titulo = it.get("titulo") or "(sem título)"
    url = it.get("url") or SITE_VOTACAO

    img = (f'<img src="{foto}" width="120" height="120" '
           f'style="border-radius:8px;object-fit:cover;display:block" alt="">') if foto else ""

    return f"""
    <table cellpadding="0" cellspacing="0" style="width:100%;border:1px solid #eee;
           border-radius:10px;margin:0 0 12px;background:#fff">
      <tr>
        <td style="padding:12px;vertical-align:top;width:132px">{img}</td>
        <td style="padding:12px 12px 12px 0;vertical-align:top;font-family:Arial,sans-serif">
          <span style="display:inline-block;background:{cor_badge};color:#fff;font-size:11px;
                font-weight:bold;padding:3px 8px;border-radius:6px">{texto_badge}</span>
          <div style="font-size:15px;font-weight:bold;color:#111;margin:6px 0 2px">{titulo}</div>
          <div style="font-size:14px;color:#111;margin:0 0 4px">
            <b>{preco}</b> &nbsp;·&nbsp; tam {tam} &nbsp;·&nbsp; {cor}
          </div>
          {f'<div style="font-size:12px;color:#666;margin:0 0 6px">{destaques}</div>' if destaques else ''}
          {f'<div style="font-size:13px;color:#333;background:#f6f6f6;border-radius:6px;padding:7px 9px;margin:0 0 8px">{msg_neg}</div>' if msg_neg else ''}
          <a href="{url}" style="font-size:13px;color:#fff;background:#111;text-decoration:none;
             padding:7px 12px;border-radius:6px">Ver no Vinted →</a>
          &nbsp;
          <a href="{SITE_VOTACAO}" style="font-size:13px;color:#0a66c2;text-decoration:none">abrir votação</a>
        </td>
      </tr>
    </table>"""


def corpo_html(marca_label: str, itens: list[dict]) -> str:
    n = len(itens)
    n_urg = sum(1 for it in itens if (it.get("negociacao") or {}).get("comprar_ja"))
    cards = "".join(_card_html(it) for it in itens)
    sub = f"{n} nova(s) oferta(s) — {marca_label}"
    if n_urg:
        sub += f" · {n_urg} ⚡ urgente(s)"
    return f"""\
<div style="max-width:640px;margin:0 auto;font-family:Arial,sans-serif;background:#fafafa;padding:16px">
  <h2 style="font-size:18px;color:#111;margin:0 0 4px">🛍️ {sub}</h2>
  <p style="font-size:12px;color:#888;margin:0 0 16px">
    Radar Didi — detectadas nesta rodada do cron.
    <a href="{SITE_VOTACAO}">votacao-two.vercel.app</a>
  </p>
  {cards}
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
