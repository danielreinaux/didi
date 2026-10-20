"""Lê data/coleta.json, classifica cada item via OpenAI Vision, salva em
data/coleta-classificada.json. Não re-scrapeia.

Pipeline por item:
  1. Prefilter de título (regex, sem IA)
  2. Verifica marca Sundek + formato (vision)
  3. Liso/estampado/logo_grande (vision)
  4. Cor tier (vision, só nos lisos aprovados)
  5. Elástico + Etiqueta (vision, só nos lisos aprovados)

Uso: python -m src.classify_run [--workers N]   (padrão: 8)
"""
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .tipo import classificar_item
from .bolso import verificar_bolso
from .brand import verificar_sundek, motivo_recheck, aceita_recheck
from .cor import classificar_cor
from .elastico import verificar_elastico
from .botao_fly import verificar_botao, verificar_velcro
from .etiqueta import verificar_etiqueta
from .listra import verificar_listra, precisa_confirmar, confirmar_faixa_unica
from ..utils.cost_tracker import track as _track, relatorio as _relatorio, dump_json as _dump_cost
from ..utils.listra_tier import avaliar_combo
from .prefilter import parece_short

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

_print_lock = threading.Lock()
_counters_lock = threading.Lock()


def _salvar(resultados: list, itens_orig: list, acervo_previo: dict, path: Path) -> None:
    """Acumula por id: acervo prévio + resultados desta rodada (que sobrescrevem).
    Itens já vistos e AUSENTES do scrape atual são PRESERVADOS — nada se perde.
    Marca status/timestamps; reaparecer no scrape reativa (status='ativo')."""
    por_idx = {i: r for i, r in resultados}
    agora = datetime.now(timezone.utc).isoformat()
    acervo = dict(acervo_previo)  # id -> item (cópia)
    for i, item in enumerate(itens_orig):
        rid = item.get("id")
        if not rid:
            continue  # stub de scrape sem id — não acumula
        if i in por_idx:
            novo = por_idx[i]
        elif rid in acervo:
            novo = acervo[rid]  # cacheado (fotos iguais) — mantém classificação
        else:
            novo = item
        prev = acervo.get(rid, {})
        novo["primeiro_visto"] = prev.get("primeiro_visto") or prev.get("coletado_em") or agora
        novo["ultimo_visto"] = agora
        novo["status"] = "ativo"  # reapareceu no scrape → ativo
        acervo[rid] = novo
    with _print_lock:
        path.write_text(json.dumps(list(acervo.values()), indent=2, ensure_ascii=False))


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def _processar(item: dict, idx: str, total: int) -> tuple[dict, int, int]:
    """Processa um item completo. Retorna (resultado, input_tokens, output_tokens)."""
    titulo = (item.get("titulo") or "")[:50]
    prefix = f"  [{idx}/{total}] {titulo}"
    in_tok = out_tok = 0

    if item.get("erro"):
        _log(f"{prefix} → SKIP (item com erro)")
        return item, 0, 0

    # 1. Prefilter
    pre = parece_short(item)
    if not pre.ok:
        tipo_pre = pre.categoria or "nao_short"
        tag = "TAMANHO" if tipo_pre == "tamanho_invalido" else "NAO-SHORT"
        _log(f"{prefix} → × {tag} [{pre.motivo}]")
        return {**item, "classificacao": {"tipo": tipo_pre, "motivo": pre.motivo, "confianca": 1}}, 0, 0

    # 2. Marca + formato
    try:
        from ..config import IA as _IA
        marca = verificar_sundek(item)
        u = marca.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("brand", _IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))

        # Double-check: mini tem falsos negativos de marca (em detail=low não reconhece
        # o logo do sol sem texto). Re-verifica com gpt-4o (detail=high) quando o mini
        # disse "não-Sundek" e o título tem "sundek" OU ele não identificou outra marca.
        motivo_rc = motivo_recheck(item, marca)
        if motivo_rc:
            marca_4o = verificar_sundek(item, model=_IA["model_detalhes"])
            u = marca_4o.pop("_usage", {})
            in_tok += u.get("prompt_tokens", 0)
            out_tok += u.get("completion_tokens", 0)
            _track("brand_4o_recheck", _IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            if aceita_recheck(motivo_rc, marca_4o):
                marca_4o["evidencia"] = "[double-check gpt-4o] " + (marca_4o.get("evidencia") or "")
                marca = marca_4o
    except Exception as e:
        # Falha na checagem de marca (ex: 429) → marca o item como erro para
        # ser reprocessado. NÃO segue em frente — sem saber se é short/Sundek,
        # o resto do pipeline não faz sentido.
        _log(f"{prefix} → ERRO marca: {str(e)[:80]}")
        return {**item, "classificacao": {"tipo": "erro", "erro": f"marca: {e}"}}, in_tok, out_tok

    # Checa formato ANTES da marca: o modelo confunde "não é short" com "não é Sundek".
    # Uma camiseta/regata Sundek deve cair em nao_short, não em nao_sundek.
    if marca.get("e_short") == "nao":
        f = marca.get("formato_identificado") or "outro"
        _log(f"{prefix} → × NAO-SHORT-VISUAL [{f}]")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_short", "motivo": f"vision: {f}"}}, in_tok, out_tok

    if marca.get("e_sundek") == "nao":
        m = marca.get("marca_identificada") or "outra marca"
        _log(f"{prefix} → × NAO-SUNDEK [{m}]")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "nao_sundek", "motivo": m}}, in_tok, out_tok

    # 3. Liso/estampado
    try:
        c = classificar_item(item)
        u = c.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        _track("classify_tipo", _IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))

        tipo_original = c.get("tipo")
        # Desbotado rebaixa só o LISO (e o indefinido). Estampado/logo_grande desbotado
        # continua com o tipo real (já é excluído pelo tipo; a aparência fica registrada
        # e o score exclui por "desbotado" de qualquer jeito) — mesma convenção do gabarito.
        if c.get("aparencia") == "desbotado" and tipo_original in ("liso", "indefinido", None):
            c["tipo_original"] = tipo_original
            c["tipo"] = "desbotado"

        tipo = c.get("tipo")
        tag = (
            "✓ LISO" if tipo == "liso"
            else "✗ EST" if tipo == "estampado"
            else "✗ LOGO" if tipo == "logo_grande"
            else "✗ DESB" if tipo == "desbotado"
            else "? IND"
        )
        linha = f"{prefix} → {tag}"

        cor = elastico = etiqueta = None

        if tipo == "liso":
            # 4. Cor PRIMEIRO — se ruim, corta antes de gastar listra/bolso/elástico
            try:
                cor = classificar_cor(item)
                u = cor.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                _track("color", _IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            except Exception as e:
                cor = {"tier": "erro", "erro": str(e)}

            # Short-circuit: cor ruim → pula listra, bolso, elástico, etiqueta
            # (cores ruins são neon/fluo — listras neutras não salvam, ver listra_tier)
            if cor and cor.get("tier") == "ruim":
                combo = avaliar_combo(cor.get("cor_principal", ""), [], cor.get("tier", ""))
                cor["cores_listras"] = []
                cor["listra_tier"] = combo["listra_tier"]
                cor["tier_final"] = combo["tier_final"]
                cor["combo_motivo"] = combo["motivo"]
                linha += f" | cor={cor.get('cor_principal')} [ruim] ✗ skip listra/bolso/elas/etiq"
                _log(linha)
                return {**item, "marca_check": marca, "classificacao": c, "cor": cor, "elastico": None, "etiqueta": None}, in_tok, out_tok

            # 4b. Listra Sundek (prompt dedicado — distingue listra real de piping)
            try:
                listra = verificar_listra(item)
                u = listra.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                _track("listra", _IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                c["cores_listras"] = listra.get("cores") or []
                c["e_piping"] = listra.get("e_piping", False)
                c["tem_listra_lateral_sundek"] = listra.get("e_listra_sundek", False)
                c["bicolor"] = listra.get("bicolor", False)
                c["listra_evidencia"] = listra.get("evidencia")
                tag_listra = (
                    "listra✓" if listra.get("e_listra_sundek")
                    else "piping" if listra.get("e_piping")
                    else "s/listra"
                )
                linha += f" | {tag_listra}"
            except Exception as e:
                pass  # mantém o que veio do prompt multi-uso

            # Ajusta tier com base na combinação cor+listras
            cores_listras = c.get("cores_listras") or []
            combo = avaliar_combo(cor.get("cor_principal", ""), cores_listras, cor.get("tier", ""))
            cor["cores_listras"] = cores_listras
            cor["listra_tier"] = combo["listra_tier"]
            cor["tier_final"] = combo["tier_final"]
            cor["combo_motivo"] = combo["motivo"]
            linha += f" | cor={cor.get('cor_principal')} [{cor.get('tier')}→{combo['tier_final']}]"

            # Short-circuit: sem listra Sundek real (ou piping) → será descartado.
            # Pula elástico, bolso e etiqueta (economiza ~$0.08/item).
            if not c.get("tem_listra_lateral_sundek") or c.get("e_piping"):
                linha += " | ✗ sem listra → skip elas/bolso/etiq"
                _log(linha)
                return {**item, "marca_check": marca, "classificacao": c, "cor": cor, "elastico": None, "etiqueta": None}, in_tok, out_tok

            # 4c. Elástico (pode excluir por botão/velcro — roda antes do bolso, mais caro)
            try:
                elastico = verificar_elastico(item)
                u = elastico.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                _track("elastico", _IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                linha += f" | {'elás✓' if elastico.get('tem_elastico') else '!SEM-ELÁS'}"
            except Exception as e:
                elastico = {"tem_elastico": None, "erro": str(e)}

            # 4c'. Detector dedicado de botão/snap no fly (feedback do cliente: "muitos com
            # BOTÃO passando" — o snap do modelo elástico+snap é pequeno e some em detail=low).
            # Zoom da cintura frontal + foto de frente em high. Só roda se o elástico não
            # já excluiu E o cós tem elástico (os 21 casos "botão" do cliente são TODOS o
            # modelo elástico+snap; boardshort de cós fixo com botão o prompt de elástico já
            # pega) → ~metade do custo. tem_botao=None (sem foto de frente) NÃO exclui.
            if ((elastico or {}).get("tipo_fechamento") not in ("botao", "velcro")
                    and (elastico or {}).get("tem_elastico") is not False):
                try:
                    bt = verificar_botao(item)
                    u = bt.pop("_usage", {})
                    bt.pop("_crop", None)
                    in_tok += u.get("prompt_tokens", 0)
                    out_tok += u.get("completion_tokens", 0)
                    _track("botao_fly", _IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                    if elastico is not None:
                        elastico["botao_fly"] = {k: bt.get(k) for k in ("tem_botao", "tipo", "o_que_vi_no_centro", "evidencia", "_crop_modo")}
                        if bt.get("tem_botao") is True:
                            elastico["tipo_fechamento_original"] = elastico.get("tipo_fechamento")
                            elastico["tipo_fechamento"] = "velcro" if bt.get("tipo") == "velcro" else "botao"
                            elastico["evidencia"] = f"[botão no fly: {bt.get('evidencia')}] " + (elastico.get("evidencia") or "")
                except Exception as e_bt:
                    print(f"  [{idx}] botao_fly falhou: {e_bt}")

            # 4c''. VELCRO nos shorts SEM elástico (boardshort de cós fixo), onde o botao_fly
            # não roda (o gate dele evita os ilhós de boardshort virarem "botão"). Velcro só
            # aparece com a braguilha ABERTA; prompt curto, fotos em low (~US$0,003/item).
            # Gabarito: 9290341091 (velcro → "cordao"). Só roda se a cor é PRETO/BRANCO:
            # sem elástico em outra cor já é excluído pelo score (sem_elastico_cor_fraca)
            # → ~70 itens/mês em vez de ~580.
            from .score import CORES_SEM_ELASTICO
            _cor_sem_el_ok = any(k in ((cor or {}).get("cor_principal") or "").lower() for k in CORES_SEM_ELASTICO)
            if (elastico is not None
                    and elastico.get("tipo_fechamento") not in ("botao", "velcro")
                    and elastico.get("tem_elastico") is False
                    and _cor_sem_el_ok):
                try:
                    vc = verificar_velcro(item)
                    u = vc.pop("_usage", {})
                    in_tok += u.get("prompt_tokens", 0)
                    out_tok += u.get("completion_tokens", 0)
                    _track("velcro_fly", _IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                    elastico["velcro_fly"] = {k: vc.get(k) for k in ("tem_velcro", "foto_braguilha_aberta", "o_que_vi", "evidencia")}
                    if vc.get("tem_velcro") is True:
                        elastico["tipo_fechamento_original"] = elastico.get("tipo_fechamento")
                        elastico["tipo_fechamento"] = "velcro"
                        elastico["evidencia"] = f"[velcro na braguilha: {vc.get('evidencia')}] " + (elastico.get("evidencia") or "")
                except Exception as e_vc:
                    print(f"  [{idx}] velcro_fly falhou: {e_vc}")

            # Short-circuit: botão/velcro → descartado. Pula bolso e etiqueta.
            if (elastico or {}).get("tipo_fechamento") in ("botao", "velcro"):
                linha += f" | ✗ {elastico.get('tipo_fechamento')} → skip bolso/etiq"
                _log(linha)
                return {**item, "marca_check": marca, "classificacao": c, "cor": cor, "elastico": elastico, "etiqueta": None}, in_tok, out_tok

            # 4d. Bolso traseiro (etapa MAIS CARA — só roda no que sobreviveu a tudo)
            try:
                bolso = verificar_bolso(item)
                u = bolso.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                _track("bolso", _IA["model_detalhes"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                c["tem_bolso_traseiro"] = bolso.get("tem_bolso")
                c["bolso_traseiro_tem_nome"] = bolso.get("tem_nome")
                c["tem_bolso_frontal"] = bolso.get("bolso_frontal", False)
                c["bolso_evidencia"] = bolso.get("evidencia")
                tag_bolso = (
                    "bolso+nome" if bolso.get("tem_nome") is True
                    else "bolso_só_logo" if bolso.get("tem_bolso") is True and bolso.get("tem_nome") is False
                    else "sem_bolso" if bolso.get("tem_bolso") is False
                    else "bolso?"
                )
                linha += f" | {tag_bolso}"
            except Exception as e:
                pass

            # 6. Etiqueta (barata, só dá bônus — por último)
            try:
                etiqueta = verificar_etiqueta(item)
                u = etiqueta.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                # etiqueta foi migrada pro mini (config conservadora)
                _track("etiqueta", _IA["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                if etiqueta.get("tem_etiqueta") is True:
                    linha += " | etiq✓"
                elif etiqueta.get("tem_etiqueta") is False:
                    linha += " | sem-etiq"
            except Exception as e:
                etiqueta = {"tem_etiqueta": None, "erro": str(e)}

        _log(linha)
        return {**item, "marca_check": marca, "classificacao": c, "cor": cor, "elastico": elastico, "etiqueta": etiqueta}, in_tok, out_tok

    except Exception as e:
        _log(f"{prefix} → ERRO: {str(e)[:80]}")
        return {**item, "marca_check": marca, "classificacao": {"tipo": "erro", "erro": str(e)}}, in_tok, out_tok


# Teto de 2ªs olhadas da listra por rodada (gpt-4o high ≈ US$ 0,0095 cada).
LISTRA_CONFIRMA_MAX_POR_RODADA = 80


def _precisa_confirmar_listra(it: dict) -> bool:
    cl = it.get("classificacao") or {}
    return ((it.get("score") or {}).get("decisao") in ("compravel", "medio")
            and (it.get("status") or "ativo") == "ativo"  # vendido/removido: não gasta
            and precisa_confirmar(cl.get("tem_listra_lateral_sundek"), cl.get("cores_listras"),
                                  "listra_confirma" in cl))


def _confirmar_listra(it: dict, calcular_score) -> None:
    """2ª olhada na listra de ≤1 cor; se for faixa de 1 cor na lateral → sem listra + rescore."""
    conf = confirmar_faixa_unica(it)
    if conf is None:  # falhou → tenta de novo na próxima rodada
        return
    u = conf.pop("_usage")
    _track("listra_confirma", u["model"], u["prompt_tokens"], u["completion_tokens"])
    cl = it.get("classificacao") or {}
    cl["listra_confirma"] = conf
    if conf["rejeitada"]:
        cl["tem_listra_lateral_sundek"] = False
        cl["faixa_unica_rejeitada"] = True
        cl["listra_evidencia"] = (
            f"faixa de 1 cor só ({', '.join(map(str, conf.get('faixas') or []))}) na "
            f"{conf.get('forma')} — não conta (decisão do cliente). [v3: {cl.get('listra_evidencia')}]")
    it["classificacao"] = cl
    if conf["rejeitada"]:
        it["score"] = calcular_score(it)


def main() -> None:
    inp = DATA / "coleta.json"
    if not inp.exists():
        print("coleta.json não encontrado. Rode `python -m src.scrape` primeiro.")
        sys.exit(1)

    workers = 8
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--workers" and i + 1 < len(sys.argv[1:]):
            workers = int(sys.argv[i + 2])

    itens = json.loads(inp.read_text())
    total = len(itens)
    print(f"=== Classificação · {total} itens · {workers} workers ===\n")

    t0 = time.time()
    resultados: list[tuple[int, dict]] = []
    input_tokens = output_tokens = 0

    # carregar acervo acumulado (TODOS já vistos, por id) + subset classificado p/ skip
    checkpoint_path = DATA / "coleta-classificada.json"
    acervo_previo: dict[str, dict] = {}
    ja_processados: dict[str, dict] = {}
    if checkpoint_path.exists():
        try:
            for x in json.loads(checkpoint_path.read_text()):
                rid = x.get("id")
                if not rid:
                    continue
                acervo_previo[rid] = x
                if (x.get("classificacao") or {}).get("tipo") not in (None, "erro"):
                    ja_processados[rid] = x
        except Exception:
            pass
    if acervo_previo:
        print(f"  acervo acumulado: {len(acervo_previo)} itens já conhecidos.")

    # Pular só se ID já processado E fotos não mudaram (mesma URL list)
    def _mesmas_fotos(item_novo: dict, item_velho: dict) -> bool:
        f_novo = tuple((item_novo.get("fotos") or []))
        f_velho = tuple((item_velho.get("fotos") or []))
        return f_novo == f_velho and bool(f_novo)

    pendentes = []
    reprocessados = 0
    for i, item in enumerate(itens):
        cached = ja_processados.get(item.get("id"))
        if cached and _mesmas_fotos(item, cached):
            continue  # mesmo item, mesmas fotos → skip
        if cached:
            reprocessados += 1  # fotos mudaram, reprocessar
        pendentes.append((i, item))

    pulados = total - len(pendentes)
    if pulados:
        print(f"  {pulados} itens já classificados (fotos idênticas) — pulando.")
    if reprocessados:
        print(f"  {reprocessados} itens com fotos modificadas — reprocessando.")
    print(f"  {len(pendentes)} itens para processar.\n")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_processar, item, f"{orig_i+1:03d}", total): (orig_i, item)
            for orig_i, item in pendentes
        }
        concluidos = 0
        for fut in as_completed(futures):
            orig_i, item_orig = futures[fut]
            try:
                resultado, in_t, out_t = fut.result()
            except Exception as e:
                resultado = {**item_orig, "classificacao": {"tipo": "erro", "erro": str(e)}}
                in_t = out_t = 0
            resultados.append((orig_i, resultado))
            with _counters_lock:
                input_tokens += in_t
                output_tokens += out_t
                concluidos += 1
                # salvar checkpoint a cada 20 itens concluídos
                if concluidos % 20 == 0:
                    _salvar(resultados, itens, acervo_previo, checkpoint_path)

    _salvar(resultados, itens, acervo_previo, checkpoint_path)

    out = json.loads(checkpoint_path.read_text())
    cnt_tipo = lambda t: sum(1 for x in out if (x.get("classificacao") or {}).get("tipo") == t)
    cnt_cor = lambda t: sum(1 for x in out if isinstance(x.get("cor"), dict) and x["cor"].get("tier") == t)

    # Custo real usando o cost_tracker (separa mini vs gpt-4o)
    # ⚠️ não use input_tokens × $0.15 — gpt-4o custa 17x mais que mini
    from ..utils.cost_tracker import _dados as _ct
    PRECOS = {"gpt-4o-mini": {"in": 0.15, "out": 0.60},
              "gpt-4o":      {"in": 2.50, "out": 10.00}}
    total_usd = 0.0
    for etapa_d in _ct.values():
        for modelo, d in etapa_d.items():
            p = PRECOS.get(modelo, {"in": 0, "out": 0})
            total_usd += (d["in"] / 1_000_000) * p["in"] + (d["out"] / 1_000_000) * p["out"]

    print("\n=== Resumo ===")
    print(f"  Não-shorts:      {cnt_tipo('nao_short')}")
    print(f"  Tamanho inválido:{cnt_tipo('tamanho_invalido')}")
    print(f"  Não-Sundek:      {cnt_tipo('nao_sundek')}")
    print(f"  Lisos:           {cnt_tipo('liso')}")
    print(f"    Maravilhoso:   {cnt_cor('maravilhoso')}")
    print(f"    Muito boa:     {cnt_cor('muito_boa')}")
    print(f"    Boa:           {cnt_cor('boa')}")
    print(f"    Ok:            {cnt_cor('ok')}")
    print(f"    Ruim:          {cnt_cor('ruim')}")
    print(f"  Desbotados:      {cnt_tipo('desbotado')}")
    print(f"  Logo grande:     {cnt_tipo('logo_grande')}")
    print(f"  Estampados:      {cnt_tipo('estampado')}")
    print(f"  Indefinidos:     {cnt_tipo('indefinido')}")
    print(f"  Erros:           {cnt_tipo('erro')}")
    print(f"  Tokens IN:       {input_tokens:,}")
    print(f"  Tokens OUT:      {output_tokens:,}")
    print(f"  Custo:           ${total_usd:.5f} (~R$ {total_usd * 5:.3f})")
    print(f"  Duração:         {time.time() - t0:.1f}s")
    print(f"\n  Salvo em data/coleta-classificada.json")

    # Relatório detalhado de custo por etapa
    print(_relatorio(total_itens=len(pendentes) or total))
    # Salva o dump em arquivo pra consulta posterior
    try:
        (DATA / "custo_por_etapa.json").write_text(json.dumps(_dump_cost(), indent=2))
    except Exception:
        pass

    # Recalcula combo (cor+listra) E score em TODOS os itens — inclusive os pulados
    # por checkpoint. Ambos são funções puras sobre o dado já salvo (sem API), então
    # mudanças em listra_tier.py / score.py propagam pros itens antigos a cada run.
    from .score import calcular_score
    from ..utils.listra_tier import avaliar_combo
    final = json.loads(checkpoint_path.read_text())
    n_confirma = 0
    for it in final:
        cor = it.get("cor")
        if isinstance(cor, dict) and cor.get("tier"):
            combo = avaliar_combo(cor.get("cor_principal", "") or "", cor.get("cores_listras") or [], cor.get("tier"))
            cor["listra_tier"] = combo["listra_tier"]
            cor["tier_final"] = combo["tier_final"]
            cor["combo_motivo"] = combo["motivo"]
        if not it.get("manual_exclusao"):
            it["score"] = calcular_score(it)
            # Faixa de UMA cor só na lateral não conta (cliente, out/2026; só com
            # LISTRA_FAIXA_UNICA="nao_conta"). A 2ª olhada (gpt-4o) roda SÓ em quem iria
            # PASSAR com listra de ≤1 cor — o resto já é descartado por outro motivo e a
            # resposta não mudaria a decisão. Na 1ª rodada cobre os ativos (backfill).
            if n_confirma < LISTRA_CONFIRMA_MAX_POR_RODADA and _precisa_confirmar_listra(it):
                n_confirma += 1
                _confirmar_listra(it, calcular_score)
    if n_confirma:
        print(f"  listra 2ª olhada (faixa de 1 cor): {n_confirma} item(ns) conferidos com gpt-4o")
    checkpoint_path.write_text(json.dumps(final, indent=2, ensure_ascii=False))

    # Auto-double-check com gpt-4o (reclassify_ambiguos) DESLIGADO (out/2026):
    #  - o prompt de tipo não devolve mais bicolor/cores_listras/tem_bolso_frontal, e o
    #    double-check sobrescrevia esses campos com False/[] (4.947 itens no acervo:
    #    bicolor apagado — ex. 9282863282 "misto, não é somente azul" passou —, cores
    #    das listras apagadas → listra_tier errado);
    #  - gpt-4o marca tecido_brilhoso=true em 15/43 compráveis do gabarito (humano: não)
    #    → 113 lisos com listra descartados SÓ por "brilhoso" depois do double-check.
    # Para reativar, só com a versão corrigida do script e medição no gabarito.
    if os.environ.get("SUNDEK_DOUBLE_CHECK") == "1":
        print("\n=== Double-check automático com gpt-4o ===")
        from .reclassify_ambiguos import main as reclassify_main
        import sys as _sys
        _argv = _sys.argv
        _sys.argv = ["reclassify_ambiguos"]
        try:
            reclassify_main()
        finally:
            _sys.argv = _argv

    # Re-dump do custo por etapa: agora inclui o double-check gpt-4o (o dump acima
    # roda antes da reclassificação, então não capturava esse gasto).
    try:
        (DATA / "custo_por_etapa.json").write_text(json.dumps(_dump_cost(), indent=2))
    except Exception:
        pass


if __name__ == "__main__":
    main()
