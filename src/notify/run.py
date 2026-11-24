"""Detecta candidatos novos no items.json e dispara um email-resumo por rodada.

Uso:
    python -m src.notify.run --marca sundek
    python -m src.notify.run --marca vilebrequin
    python -m src.notify.run --marca sundek --dry-run   # não envia, só imprime
    python -m src.notify.run --marca sundek --seed       # popula ledger sem enviar

Roda no fim de cada job do cron (depois de votacao_items gerar o items.json).
O ledger (data/notificados.json) deduplica entre rodadas; a 1ª rodada de cada
marca entra em modo seed automático pra não floodar com os candidatos já existentes.

Desde 24/11/2026 cada job avisa a sua marca: o job sundek roda `--marca sundek` e grava o
data/notificados.json; o job ville roda `--marca vilebrequin` logo depois da análise dele e grava o
data/notificados-ville.json (ledger.py). "Já avisado" vale pelos dois registros juntos.
"""
import argparse
import sys

from ..config import VILLE_ATIVA, VILLE_EMAIL
from . import email as mailer
from . import ledger as led
from .select import candidatos, novos

MARCA_LABEL = {"sundek": "Sundek", "vilebrequin": "Vilebrequin"}


def main() -> None:
    # Evita UnicodeEncodeError ao imprimir emojis (🛍️/⚡) no console Windows (cp1252).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--marca", choices=["sundek", "vilebrequin"], default=None,
                    help="filtra o items.json por marca (default: todas)")
    ap.add_argument("--dry-run", action="store_true", help="não envia email, só mostra")
    ap.add_argument("--seed", action="store_true",
                    help="marca os candidatos atuais como já vistos, sem enviar")
    args = ap.parse_args()

    # Registro desta marca (gravado) + o da outra (só lido): "já avisado" vale pelos dois juntos.
    caminho = led.LEDGER_VILLE_PATH if args.marca == "vilebrequin" else led.LEDGER_PATH
    outro = led.LEDGER_PATH if args.marca == "vilebrequin" else led.LEDGER_VILLE_PATH
    ledger = led.carregar(caminho)
    visto = {**led.carregar(outro), **ledger}
    todos = candidatos(None)
    itens = [it for it in todos if it.get("marca") == args.marca] if args.marca else todos
    # Poda pelo app inteiro, não só pela marca deste job: o notificados.json ainda guarda Ville
    # antiga, e esquecer uma que segue no app faria o job ville reavisá-la.
    manter = {str(it.get("id")) for it in todos}
    # Ville em modo sombra (config.VILLE_EMAIL): fica no app, fora do e-mail. Os candidatos dela
    # entram no registro sem envio — quando o e-mail ligar, só os anúncios novos vão.
    sombra = []
    if not VILLE_EMAIL:
        sombra = [it for it in itens if it.get("marca") == "vilebrequin" and str(it.get("id")) not in visto]
        itens = [it for it in itens if it.get("marca") != "vilebrequin"]
        if args.marca == "vilebrequin":
            print("[Ville] e-mail desligado (modo sombra, config.VILLE_EMAIL).")
    # Rótulo do rodapé do e-mail: o mesmo de antes da separação (o assunto e o título já usam a
    # marca que veio de fato). O do log diz qual job está falando.
    label = "Sundek e Vilebrequin" if VILLE_ATIVA and VILLE_EMAIL else MARCA_LABEL.get(args.marca, "Sundek")
    rotulo = MARCA_LABEL.get(args.marca, label)
    pendentes = novos(itens, visto)
    if sombra and not args.dry_run:
        led.registrar(ledger, sombra, "vilebrequin")
        led.salvar(ledger, caminho)
        print(f"[Ville] {len(sombra)} candidato(s) no app, sem e-mail (modo sombra).")

    # --dry-run: preview puro, SEM efeito colateral (não envia, não grava ledger).
    # Com ledger vazio, "novos" = todos os candidatos — útil pra ver o que sairia.
    if args.dry_run:
        modo = "seed (1ª vez — não enviaria)" if not led.ja_viu_marca(visto, args.marca) else "envio"
        print(f"[dry-run {rotulo}] modo={modo} · {len(itens)} candidatos · {len(pendentes)} novo(s):")
        if pendentes:
            print("  assunto:", mailer.assunto_premiado(pendentes) or "(oferta comum)")
        for it in pendentes:
            urg = " ⚡" if (it.get("negociacao") or {}).get("comprar_ja") else ""
            if (it.get("premiado") or {}).get("modelo"):
                urg += " 🚨 PREMIADO URGENTE" if it["premiado"].get("urgente") else " ⭐ PREMIADO"
            print(f"  - {it.get('decisao', ''):9} {it.get('preco', ''):>10}  {it.get('titulo', '')[:55]}{urg}")
        return

    # 1ª vez pra essa marca (ou --seed): registra tudo sem enviar, evitando flood.
    if args.seed or not led.ja_viu_marca(visto, args.marca):
        led.registrar(ledger, itens, args.marca)
        led.podar(ledger, manter=manter)
        led.salvar(ledger, caminho)
        print(f"[seed {rotulo}] {len(itens)} candidato(s) marcados sem enviar email.")
        return

    if not pendentes:
        print(f"[{rotulo}] nada novo ({len(itens)} candidatos, todos já avisados).")
        return

    n_urg = sum(1 for it in pendentes if (it.get("negociacao") or {}).get("comprar_ja"))
    assunto = (mailer.assunto_premiado(pendentes)
               or mailer.assunto_comum(pendentes, label) + (f" ({n_urg} ⚡)" if n_urg else ""))
    html = mailer.corpo_html(label, pendentes)

    mailer.enviar(assunto, html)
    # Só registra DEPOIS de enviar com sucesso (se falhar, reenvía na próxima rodada).
    led.registrar(ledger, pendentes, args.marca)
    led.podar(ledger, manter=manter)
    led.salvar(ledger, caminho)
    print(f"[{rotulo}] email enviado com {len(pendentes)} oferta(s).")


if __name__ == "__main__":
    main()
