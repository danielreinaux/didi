"""Guard-rail do scrape: detecta quebra silenciosa de extração.

Motivação: em 09/09/2026 o Vinted trocou o HTML da galeria e o `extract_item`
passou a devolver `fotos: []` para 100% dos itens. Nada estourou — o workflow
continuou VERDE por 3 dias, porque sem foto o classify devolve "indefinido" na
hora, sem nem chamar a OpenAI (custo R$ 0,00). O site congelou e ninguém soube.

A regra aqui é simples: se a maioria dos itens coletados vier sem foto, isso não
é o mundo real (anúncio no Vinted sem nenhuma foto é raríssimo) — é o seletor que
quebrou. Aí o step falha de propósito, o Actions fica vermelho e o problema
aparece no mesmo dia.

Importante: chamar SEMPRE depois de salvar o JSON e de atualizar o histórico —
a ideia é falhar o step, não perder o que já foi coletado.
"""
import sys

# Fração máxima tolerada de itens sem foto antes de considerar o scrape quebrado.
# 0.5 dá bastante folga: no normal isso fica perto de 0%.
LIMITE_SEM_FOTO = 0.5

# Abaixo disso a amostra é pequena demais pra concluir qualquer coisa (evita
# alarme falso numa rodada em que o Vinted devolveu 2 ou 3 anúncios).
MINIMO_AMOSTRA = 10


def checar_fotos(coletados: list[dict], origem: str) -> None:
    """Falha o processo se a extração de fotos tiver quebrado.

    `coletados` é a lista crua do scrape (itens com "erro" são ignorados, porque
    ali a falha é de rede/página, não do seletor).
    """
    validos = [i for i in coletados if not i.get("erro")]
    if len(validos) < MINIMO_AMOSTRA:
        print(f"\n[guard] {origem}: amostra pequena ({len(validos)} itens) — checagem de fotos pulada.")
        return

    sem_foto = [i for i in validos if not i.get("fotos")]
    frac = len(sem_foto) / len(validos)
    print(f"\n[guard] {origem}: {len(sem_foto)}/{len(validos)} itens sem foto ({frac:.0%}).")

    if frac <= LIMITE_SEM_FOTO:
        return

    # ::error:: faz o GitHub Actions destacar a mensagem no resumo do run.
    print(
        f"::error::[guard] {origem}: {frac:.0%} dos itens vieram sem foto "
        f"(limite: {LIMITE_SEM_FOTO:.0%}). O seletor de fotos do Vinted provavelmente "
        f"mudou — ver src/scrape/extract.py. Sem foto a IA não classifica nada e o "
        f"site para de receber itens novos."
    )
    for i in sem_foto[:3]:
        print(f"::error::[guard] exemplo sem foto: {i.get('url')}")
    sys.exit(1)
