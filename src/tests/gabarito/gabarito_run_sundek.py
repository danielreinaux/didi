"""Roda a IA nos 50 itens do gabarito SUNDEK e salva uma RODADA — igual ao
gabarito_run (Ville), mas com o pipeline Sundek e SEM os short-circuits de custo.

Diferença crucial pro pipeline de produção (classify/run.py):
  Produção faz early-exit pra economizar (cor ruim → pula listra/bolso/elás/etiq;
  sem listra → pula elás/bolso/etiq; botão → pula bolso/etiq; estampado → pula tudo).
  Isso enche os critérios de `n_a` (a etapa nem rodou) e QUEBRA a métrica de prompt.

Aqui, como no Ville: passou do PORTÃO (é Sundek + é short), roda TODOS os 7 agentes
com IA em todo item — cada critério ganha uma resposta de verdade pra comparar com
o gabarito. Também PULO o prefilter de título/tamanho (early-exit sem IA) pra medir
o prompt de marca em todos os itens.

Lever de custo (igual Ville): auto-detecção por hash. O baseline roda tudo e guarda
o hash de cada prompt; numa rodada nova, re-roda SÓ os agentes cujo prompt mudou
(+ cascata da marca, que define o portão). O resto é copiado do baseline.

Uso:
  # 1) referência (uma vez, roda os 7 agentes nos 50):
  python -m src.tests.gabarito.gabarito_run_sundek --label sundek-baseline

  # 2) depois de mexer nos prompts (auto-detecta o que mudou vs baseline):
  python -m src.tests.gabarito.gabarito_run_sundek

  # forçar áreas / tudo:
  python -m src.tests.gabarito.gabarito_run_sundek --so listra,elastico
  python -m src.tests.gabarito.gabarito_run_sundek --label sundek-v9 --all
"""
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Agentes Sundek (mesmas funções que a produção usa em classify/run.py).
from ...classify.brand import verificar_sundek
from ...classify.tipo import classificar_item
from ...classify.cor import classificar_cor
from ...classify.listra import verificar_listra
from ...classify.elastico import verificar_elastico
from ...classify.bolso import verificar_bolso
from ...classify.etiqueta import verificar_etiqueta
from ...config import IA as _IA

# Infra genérica reaproveitada do runner do Ville (fotos base64, versionamento,
# resume, carga de inputs — tudo parametrizado por dataset).
from .gabarito_run import (
    _arg, _foto_para_url, _montar_inputs, _carregar_rodada,
    _proxima_versao, SRC, REG,
)

DATASET = "sundek"

# 15 chaves — as MESMAS que o gabarito_sundek grava no campo `ia` (14 avaliadas
# + cor_nome de contexto). Assim a rodada casa 1:1 com o formato do gabarito.
CRITERIOS = [
    "e_sundek", "e_short", "tipo", "aparencia", "tecido_brilhoso", "listra",
    "bicolor", "cor_tier", "cor_nome", "tem_elastico", "fechamento",
    "bolso_traseiro", "bolso_nome", "bolso_frontal", "etiqueta",
]
# Tudo que morre quando o item é barrado no portão (não é Sundek / não é short).
DOWNSTREAM = [c for c in CRITERIOS if c not in ("e_sundek", "e_short")]

# Agente → função de classificação.
FN = {
    "marca": verificar_sundek,
    "tipo": classificar_item,
    "cor": classificar_cor,
    "listra": verificar_listra,
    "elastico": verificar_elastico,
    "bolso": verificar_bolso,
    "etiqueta": verificar_etiqueta,
}
# Agente → arquivos que compõem o hash (prompt + wrapper). Mudou → re-roda.
ARQUIVOS = {
    "marca": ["prompts/verifica_sundek.py", "classify/brand.py"],
    "tipo": ["prompts/liso_vs_estampado.py", "classify/tipo.py"],
    "cor": ["prompts/cor_tier.py", "classify/cor.py"],
    "listra": ["prompts/listra_sundek.py", "classify/listra.py"],
    "elastico": ["prompts/elastico.py", "classify/elastico.py"],
    "bolso": ["prompts/bolso_traseiro.py", "classify/bolso.py"],
    "etiqueta": ["prompts/etiqueta.py", "classify/etiqueta.py"],
}
ORDEM = ["marca", "tipo", "cor", "listra", "elastico", "bolso", "etiqueta"]
# Agente → critérios que produz (pra copiar do baseline o que não re-rodou).
AGENTE_CRITS = {
    "marca": ["e_sundek", "e_short"],
    "tipo": ["tipo", "aparencia", "tecido_brilhoso"],
    "cor": ["cor_tier", "cor_nome"],
    "listra": ["listra", "bicolor"],
    "elastico": ["tem_elastico", "fechamento"],
    "bolso": ["bolso_traseiro", "bolso_nome", "bolso_frontal"],
    "etiqueta": ["etiqueta"],
}
# A marca define o portão de TODOS → se o prompt de marca muda, re-roda tudo.
CASCATA = {"marca": list(ORDEM)}

_lock = threading.Lock()


def _hash_agente(agente: str) -> str:
    h = hashlib.sha1()
    for rel in ARQUIVOS[agente]:
        h.update((SRC / rel).read_bytes())
    return h.hexdigest()[:12]


def _hashes_atuais() -> dict:
    return {a: _hash_agente(a) for a in ORDEM}


def _b(val):
    """bool → sim/nao; None → indefinido. (Mesma convenção do gabarito_sundek.)"""
    if val is True:
        return "sim"
    if val is False:
        return "nao"
    return "indefinido"


def _campo(bloco: dict, chave: str):
    """sim/nao/indefinido se a chave existe; None se o agente nem produziu."""
    return _b(bloco.get(chave)) if chave in bloco else None


def _processar(item: dict, rodar: set, base: dict | None) -> tuple[dict, int, int]:
    """Classifica um item rodando só os agentes em `rodar`; o resto vem de `base`.
    SEM short-circuit: passou do portão, roda todos os agentes de `rodar`."""
    out = {c: (base.get(c) if base else None) for c in CRITERIOS}
    gate = (base or {}).get("_gate")
    in_tok = out_tok = 0

    # Lazy: fotos em base64 só agora (por item), liberadas ao fim do worker.
    fotos = [_foto_para_url(f) for f in item.get("fotos_local", [])]
    item = {
        "id": item.get("id"), "titulo": item.get("titulo"), "cor": item.get("cor"),
        "tamanho": item.get("tamanho"), "estado": item.get("estado"), "fotos": fotos,
    }

    def chamar(agente: str) -> dict:
        nonlocal in_tok, out_tok
        res = FN[agente](item)
        u = res.pop("_usage", {}) if isinstance(res, dict) else {}
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
        return res

    # ── MARCA + portão (é Sundek? é short?) ──────────────────────────
    if "marca" in rodar:
        marca = chamar("marca")
        # Double-check da produção: mini erra marca; se disse "não-Sundek" mas o
        # título tem "sundek", re-verifica com gpt-4o.
        titulo_lower = (item.get("titulo") or "").lower()
        if marca.get("e_sundek") == "nao" and "sundek" in titulo_lower:
            marca_4o = verificar_sundek(item, model=_IA["model_detalhes"])
            u = marca_4o.pop("_usage", {})
            in_tok += u.get("prompt_tokens", 0)
            out_tok += u.get("completion_tokens", 0)
            if marca_4o.get("e_sundek") != "nao":
                marca = marca_4o
        out["e_sundek"] = marca.get("e_sundek")
        out["e_short"] = marca.get("e_short")
        # Formato ANTES da marca: uma regata Sundek é nao_short, não nao_sundek.
        if marca.get("e_short") == "nao":
            gate = "nao_short"
        elif marca.get("e_sundek") == "nao":
            gate = "nao_sundek"
        else:
            gate = None
        if gate:
            for c in DOWNSTREAM:
                out[c] = None
            out["_gate"] = gate
            return out, in_tok, out_tok

    # Portão herdado do baseline (marca não re-rodada e item estava barrado).
    if gate:
        out["_gate"] = gate
        return out, in_tok, out_tok

    # ── Passou do portão → TODOS os agentes de `rodar` (sem early-exit) ──
    if "tipo" in rodar:
        t = chamar("tipo")
        tp = t.get("tipo")
        # Igual produção: aparência desbotada rebaixa o tipo pra "desbotado".
        if t.get("aparencia") == "desbotado":
            tp = "desbotado"
        out["tipo"] = tp
        out["aparencia"] = t.get("aparencia")
        out["tecido_brilhoso"] = _campo(t, "tecido_brilhoso")

    if "cor" in rodar:
        c = chamar("cor")
        tier = c.get("tier")
        out["cor_tier"] = None if tier in ("erro", None) else tier
        out["cor_nome"] = c.get("cor_principal")

    if "listra" in rodar:
        l = chamar("listra")
        if l.get("e_listra_sundek"):
            out["listra"] = "listra_real"
        elif l.get("e_piping"):
            out["listra"] = "piping"
        else:
            out["listra"] = "sem_listra"
        out["bicolor"] = _campo(l, "bicolor")

    if "elastico" in rodar:
        e = chamar("elastico")
        out["tem_elastico"] = _campo(e, "tem_elastico")
        out["fechamento"] = e.get("tipo_fechamento")

    if "bolso" in rodar:
        b = chamar("bolso")
        tb = b.get("tem_bolso")
        out["bolso_traseiro"] = _b(tb)
        # Patch depende do bolso traseiro (3 vias, casando com o gabarito):
        #   tem bolso  → patch = sim/nao/indefinido conforme o nome no patch;
        #   SEM bolso  → patch = n_a (não existe patch pra avaliar);
        #   bolso indefinido (traseira não visível) → patch = indefinido também.
        if tb is True:
            out["bolso_nome"] = _b(b.get("tem_nome"))
        elif tb is False:
            out["bolso_nome"] = None
        else:
            out["bolso_nome"] = "indefinido"
        out["bolso_frontal"] = _campo(b, "bolso_frontal")

    if "etiqueta" in rodar:
        et = chamar("etiqueta")
        out["etiqueta"] = _campo(et, "tem_etiqueta")

    out["_gate"] = None
    return out, in_tok, out_tok


def _definir_rodar(label: str, base_label: str) -> tuple[set, dict | None, dict]:
    """Decide quais agentes rodar e devolve (rodar, base_itens, hashes_atuais)."""
    hashes = _hashes_atuais()

    if "--all" in sys.argv or label.endswith("baseline"):
        return set(ORDEM), None, hashes

    base = _carregar_rodada(base_label)
    if base and base.get("dataset") != DATASET:
        base = None

    so = _arg("--so")
    if so:
        pedidos = {x.strip() for x in so.split(",") if x.strip()}
        invalidos = pedidos - set(ORDEM)
        if invalidos:
            print(f"Agentes inválidos: {invalidos}. Use: {', '.join(ORDEM)}")
            sys.exit(1)
        rodar = set(pedidos)
        for p in list(pedidos):
            rodar |= set(CASCATA.get(p, []))
        return rodar, (base or {}).get("itens"), hashes

    if not base:
        print(f"(sem rodada base '{base_label}' — rodando TODOS os agentes)")
        return set(ORDEM), None, hashes
    antigos = base.get("prompt_hashes", {})
    mudados = {a for a in ORDEM if hashes.get(a) != antigos.get(a)}
    rodar = set(mudados)
    for m in list(mudados):
        rodar |= set(CASCATA.get(m, []))
    return rodar, base.get("itens"), hashes


def main() -> None:
    label = _arg("--label")
    if not label:
        label = _proxima_versao(DATASET) if _carregar_rodada(f"{DATASET}-baseline") else f"{DATASET}-baseline"
    base_label = _arg("--base", f"{DATASET}-baseline")
    workers = int(_arg("--workers", "3"))

    rodar, base_itens, hashes = _definir_rodar(label, base_label)
    if not rodar:
        print("Nenhum prompt mudou desde o baseline — nada pra re-rodar. ✓")
        print("(Use --all pra forçar, ou --so <area> pra escolher.)")
        return

    inputs = _montar_inputs(DATASET)
    REG.mkdir(parents=True, exist_ok=True)
    out_path = REG / f"rodada-{label}.json"

    # Resume: reaproveita itens já feitos (crash no meio não repaga). --reset zera.
    resultados: dict[str, dict] = {}
    if "--reset" not in sys.argv:
        anterior = _carregar_rodada(label)
        if anterior and isinstance(anterior.get("itens"), dict):
            resultados = dict(anterior["itens"])
    pendentes = [it for it in inputs if it["id"] not in resultados]

    print(f"=== Rodada '{label}' · dataset '{DATASET}' · {len(inputs)} itens · agentes: {sorted(rodar)} · {workers} workers ===")
    copiados = [a for a in ORDEM if a not in rodar]
    if copiados:
        print(f"  (copiando do baseline '{base_label}': {copiados})")
    if resultados:
        print(f"  resume: {len(resultados)} já feitos · {len(pendentes)} pendentes.")
    print()

    in_tok = out_tok = 0
    t0 = time.time()

    def _escrever() -> None:
        custo = (in_tok / 1_000_000) * 0.15 + (out_tok / 1_000_000) * 0.60
        out_path.write_text(json.dumps({
            "label": label,
            "dataset": DATASET,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "base": base_label if rodar != set(ORDEM) else None,
            "agentes_rodados": sorted(rodar),
            "prompt_hashes": hashes,
            "tokens_in": in_tok,
            "tokens_out": out_tok,
            "custo_usd_aprox": round(custo, 4),
            "itens": resultados,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def tarefa(item):
        base = (base_itens or {}).get(item["id"]) if base_itens else None
        crit, it_in, it_out = _processar(item, rodar, base)
        return item["id"], crit, it_in, it_out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(tarefa, it) for it in pendentes]
        feito = 0
        for fut in as_completed(futs):
            try:
                iid, crit, it_in, it_out = fut.result()
            except Exception as e:
                with _lock:
                    print(f"  ! erro num item (fica pendente, rode de novo): {str(e)[:90]}")
                continue
            with _lock:
                resultados[iid] = crit
                in_tok += it_in
                out_tok += it_out
                feito += 1
                _escrever()  # checkpoint a cada item
                if feito % 5 == 0:
                    print(f"  {feito}/{len(pendentes)}")

    _escrever()
    custo = (in_tok / 1_000_000) * 0.15 + (out_tok / 1_000_000) * 0.60
    print(f"\nOK -> {out_path}  (rodada '{label}')")
    print(f"  {len(resultados)}/{len(inputs)} itens · tokens in/out: {in_tok:,}/{out_tok:,} · custo aprox: ${custo:.4f} · {time.time()-t0:.1f}s")
    if len(resultados) < len(inputs):
        print(f"  ⚠ {len(inputs)-len(resultados)} pendentes — rode o MESMO comando de novo (resume automático).")
    print(f"  Métrica:  python -m src.tests.gabarito.gabarito_aval_sundek --label {label}")


if __name__ == "__main__":
    main()
