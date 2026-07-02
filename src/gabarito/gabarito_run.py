"""Roda a IA nos 50 itens congelados do gabarito e salva o desempenho (uma RODADA).

É o coração da medição de regressão de prompts (ver memória base-regressao-prompts).
Usa as FOTOS LOCAIS do repo (base64) — reprodutível e independente do Vinted.

Como funciona o lever de custo (auto-detecção por hash do prompt):
  - A rodada `baseline` roda os 7 agentes nos 50 e guarda o HASH de cada arquivo
    de prompt/regra.
  - Numa rodada nova, comparamos os hashes atuais com os do baseline e re-rodamos
    SÓ os agentes cujo prompt mudou (+ cascata). O resto é copiado do baseline.
  - Assim, mexer só no prompt de autenticidade custa ~1 agente × 50, não o pipeline.

Uso:
  # 1) referência (uma vez, roda tudo):
  python -m src.gabarito.gabarito_run --label baseline

  # 2) depois de mexer nos prompts (auto-detecta o que mudou vs baseline):
  python -m src.gabarito.gabarito_run --label v2

  # forçar áreas específicas (ignora o hash):
  python -m src.gabarito.gabarito_run --label v2 --so autenticidade,fecho
  # forçar tudo:
  python -m src.gabarito.gabarito_run --label v3 --all
  # comparar contra outra rodada base (default: baseline):
  python -m src.gabarito.gabarito_run --label v2 --base baseline
"""
import base64
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ..classify.ville_brand import verificar_ville
from ..classify.tartaruga import classificar_tartaruga
from ..classify.autenticidade_ville import verificar_autenticidade
from ..classify.cor import classificar_cor
from ..classify.cordao_ville import verificar_cordao
from ..classify.fecho_ville import verificar_fecho
from ..classify.etiqueta import verificar_etiqueta
from ..classify.cor_ville import bucket_cor
from ..classify.ville_run import _parece_ville, marca_sem_evidencia

SRC = Path(__file__).resolve().parent.parent
ROOT = SRC.parent
DATA = ROOT / "data"
REG = DATA / "regressao"
PUBLIC = ROOT / "votacao" / "public"
GAB_JSON = PUBLIC / "gabarito_ville.json"
COLETA = DATA / "coleta-ville-classificada.json"

CRITERIOS = [
    "e_vilebrequin", "e_short", "tipo", "fundo_padrao", "aparencia",
    "autenticidade", "cor_bucket", "cordao_cor", "fecho", "etiqueta",
]
DOWNSTREAM = ["tipo", "fundo_padrao", "aparencia", "autenticidade",
              "cor_bucket", "cordao_cor", "fecho", "etiqueta"]

# Agente → (fn, arquivos pra hash, critérios que produz).
FN = {
    "marca": verificar_ville,
    "tartaruga": classificar_tartaruga,
    "autenticidade": verificar_autenticidade,
    "cor": classificar_cor,
    "etiqueta": verificar_etiqueta,
    "cordao": verificar_cordao,
    "fecho": verificar_fecho,
}
ARQUIVOS = {
    "marca": ["prompts/verifica_ville.py"],
    "tartaruga": ["prompts/tartaruga.py"],
    "autenticidade": ["prompts/autenticidade_ville.py"],
    "cor": ["prompts/cor_tier.py", "classify/cor_ville.py"],
    "etiqueta": ["prompts/etiqueta.py"],
    "cordao": ["prompts/cordao_ville.py"],
    "fecho": ["prompts/fecho_ville.py"],
}
ORDEM = ["marca", "tartaruga", "autenticidade", "cor", "etiqueta", "cordao", "fecho"]
# Se o prompt de X mudou, re-rodar também (dependência de portão/aplicabilidade):
#   marca define o gate de tudo; tartaruga (tipo) define se autenticidade roda.
CASCATA = {"marca": list(ORDEM), "tartaruga": ["tartaruga", "autenticidade"]}

_lock = threading.Lock()


def _arg(nome: str, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _hash_agente(agente: str) -> str:
    """SHA1 curto do conteúdo dos arquivos do agente — detecta mudança de prompt."""
    h = hashlib.sha1()
    for rel in ARQUIVOS[agente]:
        h.update((SRC / rel).read_bytes())
    return h.hexdigest()[:12]


def _hashes_atuais() -> dict:
    return {a: _hash_agente(a) for a in ORDEM}


def _mime(dados: bytes) -> str:
    if dados[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


def _foto_para_url(foto: str) -> str:
    """Foto local (/gabarito_fotos/...) → data URL base64. URL remota → como está."""
    if foto.startswith("http"):
        return foto
    p = PUBLIC / foto.lstrip("/")
    dados = p.read_bytes()
    return f"data:{_mime(dados)};base64,{base64.b64encode(dados).decode('ascii')}"


def _norm_etiqueta(val) -> str | None:
    if val is True:
        return "sim"
    if val is False:
        return "nao"
    return "indefinido"  # rodou e deu null/indefinido


def _dataset_json(dataset: str) -> Path:
    """Caminho do JSON congelado do dataset (ex: gabarito_ville.json,
    gabarito_compraveis_ville.json). Mesmo formato pros dois."""
    return PUBLIC / f"gabarito_{dataset}.json"


def _montar_inputs(dataset: str) -> list[dict]:
    """Itens de entrada: campos crus + fotos LOCAIS em base64 (congeladas).
    Sem nenhum bloco de classificação antigo — os agentes rodam do zero."""
    gab = json.loads(_dataset_json(dataset).read_text(encoding="utf-8"))["itens"]
    # Só o dataset "ville" (base) vem do coleta-ville-classificada, de onde
    # puxamos titulo/cor crus. Outros (ex: compraveis fotografados à parte)
    # já trazem os campos no próprio JSON.
    crus = {}
    if dataset == "ville" and COLETA.exists():
        crus = {str(x.get("id")): x for x in json.loads(COLETA.read_text(encoding="utf-8"))}
    inputs = []
    for it in gab:
        iid = str(it["id"])
        raw = crus.get(iid, {})
        # Guarda só os CAMINHOS das fotos (leve). O base64 é montado por item,
        # na hora de classificar (lazy), pra não segurar as 50 na memória.
        inputs.append({
            "id": iid,
            "titulo": raw.get("titulo") or it.get("titulo"),
            "cor": raw.get("cor") if isinstance(raw.get("cor"), str) else None,
            "tamanho": raw.get("tamanho") or it.get("tamanho"),
            "estado": raw.get("estado") or it.get("estado"),
            "fotos_local": it.get("fotos", []),
        })
    return inputs


def _processar(item: dict, rodar: set, base: dict | None) -> tuple[dict, int, int]:
    """Classifica um item rodando só os agentes em `rodar`; o resto vem de `base`."""
    out = {c: (base.get(c) if base else None) for c in CRITERIOS}
    gate = (base or {}).get("_gate")
    in_tok = out_tok = 0

    # Lazy: carrega as fotos em base64 SÓ agora (por item). Fica só na memória
    # deste worker e é liberado ao fim — evita o MemoryError de segurar as 50.
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

    # ── MARCA + portão ───────────────────────────────────────────────
    if "marca" in rodar:
        ok, tipo_pf, _ = _parece_ville(item)
        if not ok:
            # Portão por TÍTULO (regex, sem visão): replica o ville_run.
            gate = tipo_pf
            out["e_vilebrequin"] = "nao" if tipo_pf == "nao_ville" else None
            out["e_short"] = "nao" if tipo_pf == "nao_short" else None
            for c in DOWNSTREAM:
                out[c] = None
            out["_gate"] = gate
            return out, in_tok, out_tok
        marca = chamar("marca")
        out["e_vilebrequin"] = marca.get("e_vilebrequin")
        out["e_short"] = marca.get("e_short")
        if marca.get("e_vilebrequin") == "nao":
            gate = "nao_ville"
        elif marca.get("e_short") == "nao":
            gate = "nao_short"
        elif marca_sem_evidencia(marca):
            gate = "sem_evidencia"
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

    # ── Passou do portão → demais agentes ────────────────────────────
    if "tartaruga" in rodar:
        t = chamar("tartaruga")
        out["tipo"] = t.get("tipo")
        out["fundo_padrao"] = t.get("fundo_padrao")
        out["aparencia"] = t.get("aparencia")
    tipo_atual = out["tipo"]

    if "autenticidade" in rodar:
        if tipo_atual in ("liso", "indefinido", None):
            out["autenticidade"] = "indefinido"  # sem padrão pra avaliar o bolso
        else:
            a = chamar("autenticidade")
            out["autenticidade"] = a.get("autenticidade")
    if "cor" in rodar:
        c = chamar("cor")
        cn = c.get("cor_principal")
        out["cor_bucket"] = bucket_cor(cn) if cn else None
    if "etiqueta" in rodar:
        e = chamar("etiqueta")
        out["etiqueta"] = _norm_etiqueta(e.get("tem_etiqueta"))
    if "cordao" in rodar:
        cd = chamar("cordao")
        out["cordao_cor"] = cd.get("cordao_cor")
    if "fecho" in rodar:
        f = chamar("fecho")
        out["fecho"] = f.get("tipo_fechamento")

    out["_gate"] = None
    return out, in_tok, out_tok


def _definir_rodar(label: str, base_label: str, dataset: str) -> tuple[set, dict | None, dict]:
    """Decide quais agentes rodar e devolve (rodar, base_itens, hashes_atuais)."""
    hashes = _hashes_atuais()

    if "--all" in sys.argv or label == "baseline":
        return set(ORDEM), None, hashes

    # A base só serve se for do MESMO dataset (não dá pra comparar hashes/itens
    # de datasets diferentes). Se não existe ou é de outro dataset → roda tudo.
    base = _carregar_rodada(base_label)
    if base and base.get("dataset", "ville") != dataset:
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

    # Auto-detecção por hash vs base.
    if not base:
        print(f"(sem rodada base '{base_label}' pra este dataset — rodando TODOS os agentes)")
        return set(ORDEM), None, hashes
    antigos = base.get("prompt_hashes", {})
    mudados = {a for a in ORDEM if hashes.get(a) != antigos.get(a)}
    rodar = set(mudados)
    for m in list(mudados):
        rodar |= set(CASCATA.get(m, []))
    return rodar, base.get("itens"), hashes


def _carregar_rodada(label: str) -> dict | None:
    p = REG / f"rodada-{label}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    label = _arg("--label")
    if not label:
        print("Use --label <nome> (ex: baseline, v2).")
        sys.exit(1)
    base_label = _arg("--base", "baseline")
    dataset = _arg("--dataset", "ville")
    # Default 2 (não 4): as fotos em base64 pesam na serialização; 4 em paralelo
    # num PC carregado estourou a memória. Pode subir com --workers se sobrar RAM.
    workers = int(_arg("--workers", "2"))

    if not _dataset_json(dataset).exists():
        print(f"gabarito_{dataset}.json não existe em votacao/public/.")
        sys.exit(1)

    rodar, base_itens, hashes = _definir_rodar(label, base_label, dataset)
    if not rodar:
        print("Nenhum prompt mudou desde o baseline — nada pra re-rodar. ✓")
        print("(Use --all pra forçar, ou --so <area> pra escolher.)")
        return

    inputs = _montar_inputs(dataset)
    REG.mkdir(parents=True, exist_ok=True)
    out_path = REG / f"rodada-{label}.json"

    # RESUME: se já existe uma rodada com esse label (ex.: crashou no meio),
    # reaproveita os itens já feitos e só processa os que faltam — não repaga o
    # que já rodou. Use --reset pra começar do zero.
    resultados: dict[str, dict] = {}
    if "--reset" not in sys.argv:
        anterior = _carregar_rodada(label)
        if anterior and isinstance(anterior.get("itens"), dict):
            resultados = dict(anterior["itens"])
    pendentes = [it for it in inputs if it["id"] not in resultados]

    print(f"=== Rodada '{label}' · {len(inputs)} itens · agentes: {sorted(rodar)} · {workers} workers ===")
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
            "dataset": dataset,
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
                # Item que falhou (rede/memória) NÃO é salvo → fica pendente pro
                # próximo run. Não derruba a rodada inteira.
                with _lock:
                    print(f"  ! erro num item (fica pendente, rode de novo): {str(e)[:90]}")
                continue
            with _lock:
                resultados[iid] = crit
                in_tok += it_in
                out_tok += it_out
                feito += 1
                _escrever()  # checkpoint a CADA item — crash não perde progresso
                if feito % 5 == 0:
                    print(f"  {feito}/{len(pendentes)}")

    _escrever()
    custo = (in_tok / 1_000_000) * 0.15 + (out_tok / 1_000_000) * 0.60
    print(f"\nOK -> {out_path}")
    print(f"  {len(resultados)}/{len(inputs)} itens salvos · tokens in/out: {in_tok:,}/{out_tok:,} · custo aprox: ${custo:.4f} · {time.time()-t0:.1f}s")
    if len(resultados) < len(inputs):
        print(f"  ⚠ {len(inputs)-len(resultados)} pendentes — rode o MESMO comando de novo pra completar (resume automático).")
    print(f"  Métrica desta rodada:  python -m src.gabarito.gabarito_aval --label {label}")


if __name__ == "__main__":
    main()
