"""Detecta candidatos novos no items.json e dispara um email-resumo por rodada.

Uso:
    python -m src.notify.run --marca sundek
    python -m src.notify.run --marca vilebrequin
    python -m src.notify.run --marca sundek --dry-run   # não envia, só imprime
    python -m src.notify.run --marca sundek --seed       # popula ledger sem enviar

Roda no fim de cada job do cron (depois de votacao_items gerar o items.json).
O ledger (data/notificados.json) deduplica entre rodadas; a 1ª rodada de cada
marca entra em modo seed automático pra não floodar com os candidatos já existentes.
"""
import argparse
import sys

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

    ledger = led.carregar()
    itens = candidatos(args.marca)
    label = MARCA_LABEL.get(args.marca, "Sundek+Ville")
    pendentes = novos(itens, ledger)

    # --dry-run: preview puro, SEM efeito colateral (não envia, não grava ledger).
    # Com ledger vazio, "novos" = todos os candidatos — útil pra ver o que sairia.
    if args.dry_run:
        modo = "seed (1ª vez — não enviaria)" if not led.ja_viu_marca(ledger, args.marca) else "envio"
        print(f"[dry-run {label}] modo={modo} · {len(itens)} candidatos · {len(pendentes)} novo(s):")
        for it in pendentes:
            urg = " ⚡" if (it.get("negociacao") or {}).get("comprar_ja") else ""
            print(f"  - {it.get('decisao', ''):9} {it.get('preco', ''):>10}  {it.get('titulo', '')[:55]}{urg}")
        return

    # 1ª vez pra essa marca (ou --seed): registra tudo sem enviar, evitando flood.
    if args.seed or not led.ja_viu_marca(ledger, args.marca):
        led.registrar(ledger, itens, args.marca)
        led.podar(ledger)
        led.salvar(ledger)
        print(f"[seed {label}] {len(itens)} candidato(s) marcados sem enviar email.")
        return

    if not pendentes:
        print(f"[{label}] nada novo ({len(itens)} candidatos, todos já avisados).")
        return

    n_urg = sum(1 for it in pendentes if (it.get("negociacao") or {}).get("comprar_ja"))
    assunto = f"🛍️ {len(pendentes)} nova(s) oferta(s) {label}" + (f" ({n_urg} ⚡)" if n_urg else "")
    html = mailer.corpo_html(label, pendentes)

    mailer.enviar(assunto, html)
    # Só registra DEPOIS de enviar com sucesso (se falhar, reenvía na próxima rodada).
    led.registrar(ledger, pendentes, args.marca)
    led.podar(ledger)
    led.salvar(ledger)
    print(f"[{label}] email enviado com {len(pendentes)} oferta(s).")


if __name__ == "__main__":
    main()
