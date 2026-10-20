"""BACKFILL one-off dos itens Sundek ATIVOS com as correções de out/2026.

O pipeline só reclassifica item novo (ou com foto nova), então sem isto as correções só
valeriam para anúncios novos e o app continuaria com as decisões antigas. Grupos:

  A. estragados pelo double-check gpt-4o (reclassify_ambiguos): lisos com _model=gpt-4o e
     listra. O double-check gravava False/[] em bicolor, cores_listras e tem_bolso_frontal e
     marcava brilhoso em excesso → re-roda tipo + listra (mini) e, se passar, o bolso (4o).
  B. descartados SÓ por "bolso_so_logo_colecao_antiga" → re-roda o bolso (nome fluo).
  C. comprável/médio com elástico (inclusive os que A/B liberaram) → detector de botão no fly.
  D. sem IA, em todos os ativos: lote no título (prefilter) e normalização do tier de cor.

Em DUAS etapas, porque o double-check segue ligado em produção até este branch entrar na
main — reparar o acervo antes faria ele estragar os itens de novo:
  python -m src.classify.backfill_sundek --stage data/_backfill_sundek.json   # gasta IA, não grava o acervo
  python -m src.classify.backfill_sundek --apply data/_backfill_sundek.json   # sem IA, grava o acervo
O --apply só usa o resultado da IA em itens cujas fotos não mudaram desde o --stage.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from ..config import IA
from ..utils.cost_tracker import relatorio, track
from ..utils.listra_tier import avaliar_combo
from .bolso import verificar_bolso
from .botao_fly import verificar_botao
from .cor import _normalizar_tier
from .listra import verificar_listra
from .prefilter import EXCLUSAO_LOTE
from .reclassify_ambiguos import _fotos_fingerprint
from .score import calcular_score
from .tipo import classificar_item

PATH = Path(__file__).resolve().parent.parent.parent / "data" / "coleta-classificada.json"


def _passa(it: dict) -> bool:
    return (it.get("score") or {}).get("decisao") in ("compravel", "medio")


def _alvo_dc(it: dict) -> bool:
    cl = it.get("classificacao") or {}
    return cl.get("tipo") == "liso" and cl.get("_model") == "gpt-4o" and bool(cl.get("tem_listra_lateral_sundek"))


def _alvo_bolso(it: dict) -> bool:
    return (it.get("score") or {}).get("motivo_exclusao") == "bolso_so_logo_colecao_antiga"


def _alvo_botao(it: dict) -> bool:
    el = it.get("elastico") or {}
    return _passa(it) and el.get("tem_elastico") is True and el.get("tipo_fechamento") not in ("botao", "velcro")


def _deterministico(it: dict) -> dict:
    """Grupo D (sem IA): lote no título + tier de cor normalizado; recalcula combo e score."""
    it = dict(it)
    for regex, motivo in EXCLUSAO_LOTE:
        if regex.search(it.get("titulo") or ""):
            it["marca_check"] = {**(it.get("marca_check") or {}), "lote": True, "lote_motivo": motivo}
            break
    if isinstance(it.get("cor"), dict) and it["cor"].get("tier"):
        cor = _normalizar_tier(dict(it["cor"]))
        combo = avaliar_combo(cor.get("cor_principal", "") or "",
                              (it.get("classificacao") or {}).get("cores_listras") or [], cor.get("tier", ""))
        cor.update(listra_tier=combo["listra_tier"], tier_final=combo["tier_final"], combo_motivo=combo["motivo"])
        it["cor"] = cor
    it["score"] = calcular_score(it)
    return it


def _conservador(it: dict, upd_cl: dict) -> dict:
    """O backfill RESGATA e restaura — não cria descarte novo com releitura incerta:
    - listra_na_frente que o double-check gravou era resposta real do gpt-4o (o prompt de
      tipo pede esse campo); a releitura no mini dá falso positivo → mantém a do 4o;
    - o bolso relido nunca rebaixa tem_bolso/tem_nome de True para False (patch claro com
      nome tom sobre tom é ambíguo); serve para restaurar o bolso frontal e resgatar fluo."""
    cl = it.get("classificacao") or {}
    upd_cl = {k: v for k, v in upd_cl.items() if k != "listra_na_frente"}
    for k in ("tem_bolso_traseiro", "bolso_traseiro_tem_nome"):
        if cl.get(k) is True and upd_cl.get(k) is False:
            upd_cl.pop(k)
    return upd_cl


def _aplicar(it: dict, upd: dict) -> dict:
    """Junta os campos da IA (classificacao/elastico) e roda a parte determinística."""
    novo = {**it, "classificacao": {**(it.get("classificacao") or {}),
                                    **_conservador(it, upd.get("classificacao", {}))}}
    if upd.get("elastico"):
        novo["elastico"] = {**(it.get("elastico") or {}), **upd["elastico"]}
    if isinstance(novo.get("cor"), dict):
        novo["cor"] = {**novo["cor"], "cores_listras": novo["classificacao"].get("cores_listras") or []}
    return _deterministico(novo)


def _usage(res: dict, etapa: str, modelo: str) -> dict:
    u = res.pop("_usage", {}) or {}
    track(etapa, modelo, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    return res


def _bolso(it: dict) -> dict:
    b = _usage(verificar_bolso(it), "backfill_bolso", IA["model_detalhes"])
    return {"tem_bolso_traseiro": b.get("tem_bolso"), "bolso_traseiro_tem_nome": b.get("tem_nome"),
            "tem_bolso_frontal": b.get("bolso_frontal", False), "bolso_evidencia": b.get("evidencia")}


def _backfill(it: dict) -> dict | None:
    try:
        upd, grupos = {"classificacao": {}}, []
        if _alvo_dc(it):
            grupos.append("A")
            t = _usage(classificar_item(it), "backfill_tipo", IA["model"])
            l = _usage(verificar_listra(it), "backfill_listra", IA["model"])
            upd["classificacao"].update(
                tecido_brilhoso=bool(t.get("tecido_brilhoso")), listra_na_frente=bool(t.get("listra_na_frente")),
                bicolor=bool(l.get("bicolor")), cores_listras=l.get("cores") or [], e_piping=l.get("e_piping", False),
                tem_listra_lateral_sundek=l.get("e_listra_sundek", False), listra_evidencia=l.get("evidencia"),
                _model="backfill-out2026")
            if _passa(_aplicar(it, upd)):
                upd["classificacao"].update(_bolso(it))
        elif _alvo_bolso(it):
            grupos.append("B")
            upd["classificacao"].update(_bolso(it))
        if _alvo_botao(_aplicar(it, upd)):
            grupos.append("C")
            bt = _usage(verificar_botao(it), "backfill_botao", IA["model_detalhes"])
            bt.pop("_crop", None)
            upd["elastico"] = {"botao_fly": {k: bt.get(k) for k in ("tem_botao", "tipo", "o_que_vi_no_centro", "evidencia", "_crop_modo")}}
            if bt.get("tem_botao") is True:
                upd["elastico"].update(tipo_fechamento_original=(it.get("elastico") or {}).get("tipo_fechamento"),
                                       tipo_fechamento="velcro" if bt.get("tipo") == "velcro" else "botao")
        if not grupos:
            return None
        upd["_grupos"], upd["_fotos"] = grupos, _fotos_fingerprint(it)
        return upd
    except Exception as e:  # um item com erro (ex.: foto 404) não derruba o backfill
        print(f"  {it.get('id')}: erro — {e}")
        return None


def stage(out: Path) -> None:
    ativos = [it for it in json.loads(PATH.read_text()) if it.get("status") == "ativo"]
    alvos = [it for it in ativos if _alvo_dc(it) or _alvo_bolso(it) or _alvo_botao(it)]
    print(f"ativos: {len(ativos)} · alvos com IA: {len(alvos)}")
    with ThreadPoolExecutor(3) as ex:
        res = dict(zip((str(it["id"]) for it in alvos), ex.map(_backfill, alvos)))
    mapa = {i: u for i, u in res.items() if u}
    out.write_text(json.dumps({"gerado_em": datetime.now(timezone.utc).isoformat(), "itens": mapa},
                              indent=2, ensure_ascii=False))
    print(f"OK -> {out} ({len(mapa)} itens com resultado)")
    print(relatorio(len(alvos)))


def apply(mapa_path: Path, gravar: bool = True) -> None:
    mapa = json.loads(mapa_path.read_text())["itens"]
    todos = json.loads(PATH.read_text())
    mudancas, pulou = [], 0
    for k, it in enumerate(todos):
        if it.get("status") != "ativo":
            continue
        upd = mapa.get(str(it.get("id")))
        if upd and upd.get("_fotos") != _fotos_fingerprint(it):
            upd, pulou = None, pulou + 1  # fotos mudaram: o pipeline normal reprocessa
        novo = _aplicar(it, upd) if upd else _deterministico(it)
        antes, depois = (it.get("score") or {}).get("decisao"), novo["score"].get("decisao")
        if antes != depois:
            mudancas.append((it.get("id"), antes, depois, novo["score"].get("motivo_exclusao") or "",
                             ",".join((upd or {}).get("_grupos", ["D"]))))
        todos[k] = novo
    for m in mudancas:
        print(f"  {m[0]}: {m[1]} → {m[2]} {m[3]} [{m[4]}]")
    trans = {}
    for m in mudancas:
        trans[(m[1], m[2])] = trans.get((m[1], m[2]), 0) + 1
    print(f"{len(mudancas)} decisões mudam ({pulou} itens pulados: fotos mudaram) · {trans}")
    if gravar:
        PATH.write_text(json.dumps(todos, indent=2, ensure_ascii=False))
        print(f"gravado em {PATH}")


if __name__ == "__main__":
    if "--stage" in sys.argv:
        stage(Path(sys.argv[sys.argv.index("--stage") + 1]))
    elif "--apply" in sys.argv:
        apply(Path(sys.argv[sys.argv.index("--apply") + 1]), gravar="--dry" not in sys.argv)
    else:
        print(__doc__)
