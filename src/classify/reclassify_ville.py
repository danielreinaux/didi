"""Reclassifica UMA etapa da Vilebrequin sem re-rodar o pipeline inteiro.

Lê data/coleta-ville-classificada.json, refaz a etapa pedida e recalcula o score.
Espelha os reclassify_* do Sundek.

Uso:
  python -m src.classify.reclassify_ville                 # só recalcula o SCORE (sem IA, grátis)
  python -m src.classify.reclassify_ville --etapa prefilter  # re-rotula título + renomeia (sem IA)
  python -m src.classify.reclassify_ville --etapa cor     # refaz cor + score
  python -m src.classify.reclassify_ville --etapa tartaruga --workers 8
  python -m src.classify.reclassify_ville --etapa autenticidade
  python -m src.classify.reclassify_ville --etapa autenticidade --so-original --limite 30
  python -m src.classify.reclassify_ville --etapa cordao  # refaz cor do cordão + score
  python -m src.classify.reclassify_ville --etapa marca   # refaz verifica_ville (marca + é-short + sem_evidencia)
  python -m src.classify.reclassify_ville --id 8940219584 # só um item (todas as etapas de IA)

Etapas: score (default) | prefilter | sem_evidencia | cor | tartaruga | autenticidade | cordao | marca
  prefilter = sem IA: aplica o prefilter de título novo (infantil/não-short) e
              unifica nao_vilebrequin→nao_ville (P2/P3) nos dados já coletados.
  sem_evidencia = sem IA: re-aplica a regra de "foto não mostra o produto"
              (paisagem/palmeira) sobre o marca_check já salvo → vira descartado.

Filtros (combinam com --etapa):
  --so-original  Atalho: equivale a --autenticidade original
  --autenticidade X
                 Só processa itens com classificacao.autenticidade na lista X
                 (vírgula). Valores: original | falso | suspeito | indefinido
                 | sem_foto_bolso. Ex: --autenticidade falso = só reanalisa os
                 que estão marcados como falso hoje (útil quando você refinou
                 o prompt e quer revisitar potenciais falso-positivos).
  --decisao X    Só processa itens com score.decisao na lista X (separada
                 por vírgula). Valores: compravel | medio | descartado.
                 Ex: --decisao compravel,medio = compráveis + barganhas
                 (= tudo que está hoje na página de votação).
                 Combina com --so-original.
  --limite N     Limita a uma amostra aleatória de N itens (seed fixa = 42,
                 reproduzível). Aplica DEPOIS dos outros filtros.

Quando usar: você mexeu no prompt/regra de UMA etapa e quer o efeito sem
repagar o pipeline todo. O score é sempre recalculado no fim.
"""
import json
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Console do Windows é cp1252 e quebra em ✓/✗/🐢 — força UTF-8 na saída.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from .tartaruga import classificar_tartaruga
from .autenticidade_ville import verificar_autenticidade
from .cor import classificar_cor
from .cordao_ville import verificar_cordao
from .ville_brand import verificar_ville
from .score_ville import calcular_score

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
PATH = DATA / "coleta-ville-classificada.json"

_lock = threading.Lock()


def _arg(nome: str, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _refazer_etapa(item: dict, etapa: str) -> dict:
    """Refaz a etapa de IA pedida no item (in-place no dict) e devolve."""
    tipo = (item.get("classificacao") or {}).get("tipo")

    # Etapa "marca" pode reabilitar itens que viraram sem_evidencia/nao_ville/nao_short,
    # então é a única que processa esses tipos. Demais etapas pulam.
    if etapa == "marca":
        # Pula só itens nunca classificados ou com erro técnico — todo o resto
        # pode mudar de status com a nova regra de sem_evidencia.
        if tipo in (None, "erro"):
            return item
        marca = verificar_ville(item)
        marca.pop("_usage", None)
        item["marca_check"] = marca
        e_vb = marca.get("e_vilebrequin")
        e_sh = marca.get("e_short")
        conf = marca.get("confianca") or 0
        # Replica a lógica do ville_run (B+C) — mantém os dois fluxos em sincronia.
        if e_vb == "nao":
            item["classificacao"] = {**(item.get("classificacao") or {}), "tipo": "nao_ville",
                                     "motivo": "marca diferente (visão)", "confianca": conf}
        elif e_sh == "nao":
            item["classificacao"] = {**(item.get("classificacao") or {}), "tipo": "nao_short",
                                     "confianca": conf}
        elif (e_vb == "indefinido" and conf == 0) or (
            e_vb == "indefinido" and e_sh == "indefinido" and conf < 0.4
        ):
            item["classificacao"] = {**(item.get("classificacao") or {}), "tipo": "sem_evidencia",
                                     "motivo": marca.get("evidencia") or "sem evidência visual do produto",
                                     "confianca": conf}
        # Caso já tenha passado num run anterior e a marca confirma → não mexe no tipo.
        return item

    # Só faz sentido rodar IA em itens que chegaram à classificação de padrão.
    # infantil/sem_evidencia são exclusões terminais (título / sem produto na foto):
    # re-rodar tartaruga aqui SOBRESCREVERIA o tipo e poderia ressuscitar um short
    # infantil como tartaruga. Pula sempre.
    if tipo in (None, "erro", "nao_ville", "nao_vilebrequin", "nao_short",
                "infantil", "sem_evidencia"):
        return item

    if etapa == "tartaruga":
        t = classificar_tartaruga(item)
        t.pop("_usage", None)
        item["tartaruga"] = t
        item["classificacao"] = {**(item.get("classificacao") or {}), "tipo": t.get("tipo", "indefinido")}
    elif etapa == "cor":
        c = classificar_cor(item)
        c.pop("_usage", None)
        item["cor"] = c
    elif etapa == "autenticidade":
        tipo_tart = (item.get("tartaruga") or {}).get("tipo")
        if tipo_tart in ("liso", "indefinido", None):
            item["autenticidade"] = {"autenticidade": "indefinido",
                                     "evidencia": "liso/indefinido — sem padrão de referência"}
        else:
            a = verificar_autenticidade(item)
            a.pop("_usage", None)
            item["autenticidade"] = a
        item["classificacao"] = {**(item.get("classificacao") or {}),
                                 "autenticidade": item["autenticidade"].get("autenticidade")}
    elif etapa == "cordao":
        cd = verificar_cordao(item)
        cd.pop("_usage", None)
        item["cordao"] = cd
    return item


def main() -> None:
    if not PATH.exists():
        print("coleta-ville-classificada.json não encontrado. Rode `python -m src.classify.ville_run`.")
        sys.exit(1)

    etapa = _arg("--etapa", "score")
    workers = int(_arg("--workers", "4"))
    only_id = _arg("--id")
    so_original = "--so-original" in sys.argv
    autenticidade_filtro = _arg("--autenticidade")
    if so_original and not autenticidade_filtro:
        autenticidade_filtro = "original"  # alias retrocompatível
    decisao = _arg("--decisao")
    limite = _arg("--limite")
    limite = int(limite) if limite else None

    itens = json.loads(PATH.read_text(encoding="utf-8"))
    alvos = [it for it in itens if (not only_id or str(it.get("id")) == str(only_id))]

    if decisao:
        decisoes = {d.strip() for d in decisao.split(",") if d.strip()}
        antes = len(alvos)
        alvos = [it for it in alvos
                 if (it.get("score") or {}).get("decisao") in decisoes]
        print(f"--decisao {','.join(sorted(decisoes))}: {antes} → {len(alvos)} itens")

    if autenticidade_filtro:
        valores = {v.strip() for v in autenticidade_filtro.split(",") if v.strip()}
        antes = len(alvos)
        alvos = [it for it in alvos
                 if (it.get("classificacao") or {}).get("autenticidade") in valores]
        print(f"--autenticidade {','.join(sorted(valores))}: {antes} → {len(alvos)} itens")

    if limite and len(alvos) > limite:
        # Amostra aleatória reproduzível (seed fixa) — dá variedade de cores/padrões
        # em vez de pegar só os N primeiros.
        rnd = random.Random(42)
        alvos = rnd.sample(alvos, limite)
        print(f"--limite {limite}: amostra aleatória (seed=42)")

    if etapa == "score":
        # Sem IA: só recalcula a decisão de compra em cima do que já está classificado.
        n = 0
        for it in alvos:
            it["score"] = calcular_score(it)
            n += 1
        PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Score recalculado em {n} itens (sem custo de IA).")
        _resumo(itens)
        return

    if etapa == "prefilter":
        # Sem IA: migração de dados (P2/P3). Renomeia nao_vilebrequin→nao_ville e
        # re-roda o prefilter de título pra re-tagar infantil/não-short que escaparam.
        from .ville_run import _parece_ville
        renomeados = re_tagueados = 0
        for it in alvos:
            cl = it.get("classificacao") or {}
            tipo = cl.get("tipo")
            if tipo == "nao_vilebrequin":
                cl = {**cl, "tipo": "nao_ville"}
                it["classificacao"] = cl
                tipo = "nao_ville"
                renomeados += 1
            ok, tipo_pf, motivo = _parece_ville(it)
            # Só re-tag quando o título dispara uma exclusão e o tipo atual difere
            # (ex: item que a IA deixou passar mas o título diz 'enfant'/'polo').
            if not ok and tipo != tipo_pf:
                it["classificacao"] = {**cl, "tipo": tipo_pf, "motivo": motivo}
                re_tagueados += 1
            it["score"] = calcular_score(it)
        PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Prefilter aplicado: {renomeados} renomeados (nao_vilebrequin→nao_ville), "
              f"{re_tagueados} re-tagueados por título. Score recalculado.")
        _resumo(itens)
        return

    if etapa == "sem_evidencia":
        # Sem IA: re-aplica a regra sem_evidencia sobre o marca_check já salvo.
        # Pega itens antigos (classificados antes da regra) que viraram 'indefinido'
        # quando deviam ser 'sem_evidencia' (ex.: foto só de paisagem/palmeira).
        from .ville_run import marca_sem_evidencia
        n = 0
        for it in alvos:
            cl = it.get("classificacao") or {}
            mc = it.get("marca_check") or {}
            if cl.get("tipo") != "sem_evidencia" and marca_sem_evidencia(mc):
                it["classificacao"] = {**cl, "tipo": "sem_evidencia",
                                       "motivo": mc.get("evidencia") or "sem evidência visual do produto"}
                n += 1
            it["score"] = calcular_score(it)
        PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"sem_evidencia re-aplicado: {n} itens re-tagueados (sem custo de IA).")
        _resumo(itens)
        return

    if etapa not in ("cor", "tartaruga", "autenticidade", "cordao", "marca"):
        print(f"Etapa inválida: {etapa}. Use: score | prefilter | sem_evidencia | cor | tartaruga | autenticidade | cordao | marca")
        sys.exit(1)

    print(f"=== Reclassify Ville · etapa={etapa} · {len(alvos)} itens · {workers} workers ===\n")
    feito = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_refazer_etapa, it, etapa): it for it in alvos}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"  erro no item {it.get('id')}: {e}")
            it["score"] = calcular_score(it)
            with _lock:
                feito += 1
                if feito % 20 == 0:
                    PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"  {feito}/{len(alvos)} (checkpoint salvo)")

    PATH.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOK — {feito} itens reprocessados (etapa {etapa}) + score recalculado.")
    _resumo(itens)


def _resumo(itens: list) -> None:
    dec = lambda d: sum(1 for x in itens if (x.get("score") or {}).get("decisao") == d)
    print(f"  ✓ Compráveis: {dec('compravel')} · ~ Médios: {dec('medio')} · ✗ Descartados: {dec('descartado')}")


if __name__ == "__main__":
    main()
