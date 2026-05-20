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
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .classify import classificar_item
from .classify_bolso import verificar_bolso
from .classify_brand import verificar_sundek
from .classify_color import classificar_cor
from .classify_elastico import verificar_elastico
from .classify_etiqueta import verificar_etiqueta
from .classify_listra import verificar_listra
from .listra_tier import avaliar_combo
from .prefilter import parece_short

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

_print_lock = threading.Lock()
_counters_lock = threading.Lock()


def _salvar(resultados: list, itens_orig: list, ja_processados: dict, path: Path) -> None:
    por_idx = {i: r for i, r in resultados}
    out = []
    for i, item in enumerate(itens_orig):
        if i in por_idx:
            out.append(por_idx[i])
        elif item.get("id") in ja_processados:
            out.append(ja_processados[item["id"]])
        else:
            out.append(item)
    with _print_lock:
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False))


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
        _log(f"{prefix} → × NAO-SHORT [{pre.motivo}]")
        return {**item, "classificacao": {"tipo": "nao_short", "motivo": pre.motivo, "confianca": 1}}, 0, 0

    # 2. Marca + formato
    try:
        marca = verificar_sundek(item)
        u = marca.pop("_usage", {})
        in_tok += u.get("prompt_tokens", 0)
        out_tok += u.get("completion_tokens", 0)
    except Exception as e:
        marca = {"e_sundek": "indefinido", "evidencia": f"erro: {e}", "confianca": 0}

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

        tipo_original = c.get("tipo")
        if c.get("aparencia") == "desbotado":
            c["tipo_original"] = tipo_original
            c["tipo"] = "desbotado"
        elif tipo_original == "liso" and not c.get("tem_listra_lateral_sundek"):
            c["tipo_original"] = tipo_original
            c["tipo"] = "liso_sem_listra"

        tipo = c.get("tipo")
        tag = (
            "✓ LISO" if tipo == "liso"
            else "✗ EST" if tipo == "estampado"
            else "✗ LOGO" if tipo == "logo_grande"
            else "✗ DESB" if tipo == "desbotado"
            else "✗ S/LIS" if tipo == "liso_sem_listra"
            else "? IND"
        )
        linha = f"{prefix} → {tag}"

        cor = elastico = etiqueta = None

        if tipo == "liso":
            # 3b. Listra Sundek (prompt dedicado — distingue listra real de piping)
            try:
                listra = verificar_listra(item)
                u = listra.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                c["cores_listras"] = listra.get("cores") or []
                c["e_piping"] = listra.get("e_piping", False)
                c["tem_listra_lateral_sundek"] = listra.get("e_listra_sundek", False)
                c["listra_evidencia"] = listra.get("evidencia")
                tag_listra = (
                    "listra✓" if listra.get("e_listra_sundek")
                    else "piping" if listra.get("e_piping")
                    else "s/listra"
                )
                linha += f" | {tag_listra}"
            except Exception as e:
                pass  # mantém o que veio do prompt multi-uso

            # 4. Cor
            try:
                cor = classificar_cor(item)
                u = cor.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                # Ajusta tier com base na combinação cor+listras
                cores_listras = c.get("cores_listras") or []
                combo = avaliar_combo(cor.get("cor_principal", ""), cores_listras, cor.get("tier", ""))
                cor["cores_listras"] = cores_listras
                cor["listra_tier"] = combo["listra_tier"]
                cor["tier_final"] = combo["tier_final"]
                cor["combo_motivo"] = combo["motivo"]
                linha += f" | cor={cor.get('cor_principal')} [{cor.get('tier')}→{combo['tier_final']}] listras={cores_listras}"
            except Exception as e:
                cor = {"tier": "erro", "erro": str(e)}

            # Short-circuit: se cor é ruim sem chance de salvar, pula elástico+etiqueta
            if cor and cor.get("tier_final") == "ruim":
                linha += " | ✗ cor ruim → skip elas/etiq"
                _log(linha)
                return {**item, "marca_check": marca, "classificacao": c, "cor": cor, "elastico": None, "etiqueta": None}, in_tok, out_tok

            # 4b. Bolso traseiro (prompt dedicado, sobrescreve campos da etapa 3)
            try:
                bolso = verificar_bolso(item)
                u = bolso.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                # Sobrescreve os campos do prompt multi-uso (que estava alucinando)
                c["tem_bolso_traseiro"] = bolso.get("tem_bolso")
                c["bolso_traseiro_tem_nome"] = bolso.get("tem_nome")
                c["bolso_evidencia"] = bolso.get("evidencia")
                tag_bolso = (
                    "bolso+nome" if bolso.get("tem_nome") is True
                    else "bolso_só_logo" if bolso.get("tem_bolso") is True and bolso.get("tem_nome") is False
                    else "sem_bolso" if bolso.get("tem_bolso") is False
                    else "bolso?"
                )
                linha += f" | {tag_bolso}"
            except Exception as e:
                pass  # mantém o que veio do prompt multi-uso

            # 5. Elástico
            try:
                elastico = verificar_elastico(item)
                u = elastico.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
                linha += f" | {'elás✓' if elastico.get('tem_elastico') else '!SEM-ELÁS'}"
            except Exception as e:
                elastico = {"tem_elastico": None, "erro": str(e)}

            # 6. Etiqueta
            try:
                etiqueta = verificar_etiqueta(item)
                u = etiqueta.pop("_usage", {})
                in_tok += u.get("prompt_tokens", 0)
                out_tok += u.get("completion_tokens", 0)
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

    # carregar checkpoint existente (IDs já processados)
    checkpoint_path = DATA / "coleta-classificada.json"
    ja_processados: dict[str, dict] = {}
    if checkpoint_path.exists():
        try:
            for x in json.loads(checkpoint_path.read_text()):
                if x.get("id") and (x.get("classificacao") or {}).get("tipo") not in (None, "erro"):
                    ja_processados[x["id"]] = x
        except Exception:
            pass

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
                    _salvar(resultados, itens, ja_processados, checkpoint_path)

    _salvar(resultados, itens, ja_processados, checkpoint_path)

    out = json.loads(checkpoint_path.read_text())
    cnt_tipo = lambda t: sum(1 for x in out if (x.get("classificacao") or {}).get("tipo") == t)
    cnt_cor = lambda t: sum(1 for x in out if isinstance(x.get("cor"), dict) and x["cor"].get("tier") == t)

    in_usd = (input_tokens / 1_000_000) * 0.15
    out_usd = (output_tokens / 1_000_000) * 0.60
    total_usd = in_usd + out_usd

    print("\n=== Resumo ===")
    print(f"  Não-shorts:      {cnt_tipo('nao_short')}")
    print(f"  Não-Sundek:      {cnt_tipo('nao_sundek')}")
    print(f"  Lisos:           {cnt_tipo('liso')}")
    print(f"    Maravilhoso:   {cnt_cor('maravilhoso')}")
    print(f"    Muito boa:     {cnt_cor('muito_boa')}")
    print(f"    Boa:           {cnt_cor('boa')}")
    print(f"    Ok:            {cnt_cor('ok')}")
    print(f"    Ruim:          {cnt_cor('ruim')}")
    print(f"  Liso sem listra: {cnt_tipo('liso_sem_listra')}")
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

    # Recalcula scores antes do gpt-4o (ele só roda em compráveis/ambíguos)
    from .score import calcular_score
    final = json.loads(checkpoint_path.read_text())
    for it in final:
        if not it.get("manual_exclusao"):
            it["score"] = calcular_score(it)
    checkpoint_path.write_text(json.dumps(final, indent=2, ensure_ascii=False))

    # Auto-double-check com gpt-4o em compráveis e ambíguos estruturais
    print("\n=== Double-check automático com gpt-4o ===")
    from .reclassify_ambiguos import main as reclassify_main
    import sys as _sys
    _argv = _sys.argv
    _sys.argv = ["reclassify_ambiguos"]
    try:
        reclassify_main()
    finally:
        _sys.argv = _argv


if __name__ == "__main__":
    main()
