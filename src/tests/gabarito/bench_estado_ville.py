"""Bancada do agente de CONSERVAÇÃO da Ville (desbotado + mancha) contra o gabarito (aparencia).

Uso (da raiz do repo):
  python -m src.tests.gabarito.bench_estado_ville src.prompts.estado_ville haiku_high8 --votos 3
  python -m src.tests.gabarito.bench_estado_ville src.prompts.estado_ville gem35_high8
Variantes em VAR. Tudo pelo OpenRouter. Saída: data/regressao/bench_estado/*.json.
Resultado de 05/11/2026 (77 itens, 3 desbotados): ver classify/estado_ville.py.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .gabarito_run import _foto_para_url

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
SAIDA = ROOT / "data" / "regressao" / "bench_estado"
SAIDA.mkdir(parents=True, exist_ok=True)


def itens():
    """Itens dos 2 gabaritos da Ville com a resposta humana (data/regressao/gabarito_respostas.json)."""
    truth = json.loads((ROOT / "data/regressao/gabarito_respostas.json").read_text())["respostas"]
    out = []
    for ds in ("ville", "compraveis_ville"):
        g = json.loads((ROOT / f"votacao/public/gabarito_{ds}.json").read_text())
        for it in g["itens"]:
            t = truth.get(str(it["id"]))
            if isinstance(t, dict) and t:
                out.append({**it, "_ds": ds, "_truth": t})
    return out


PRECO = {"anthropic/claude-haiku-5.5": (0.10, 0.50), "google/gemini-3.5-flash-lite": (0.30, 2.50),
         "google/gemini-3.5-flash": (1.50, 9.00), "openai/gpt-6.1-sol": (2.0, 10.0),
         "anthropic/claude-sonnet-5.5": (2.0, 10.0)}
VAR = {
    "haiku_high8": {"model": "anthropic/claude-haiku-5.5", "detail": "high", "n": 8},
    "gem35_high8": {"model": "google/gemini-3.5-flash-lite", "detail": "high", "n": 8,
                    "extra": {"reasoning": {"effort": "minimal"}}},
    "gem35f_high8": {"model": "google/gemini-3.5-flash", "detail": "high", "n": 8,
                     "extra": {"reasoning": {"effort": "low"}}},
    "sol_high8": {"model": "openai/gpt-6.1-sol", "detail": "high", "n": 8,
                  "extra": {"reasoning": {"effort": "medium"}}},
    "sonnet_high8": {"model": "anthropic/claude-sonnet-5.5", "detail": "high", "n": 8},
}
CLI = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"].strip(), base_url="https://openrouter.ai/api/v1",
             max_retries=4, timeout=180)


def chamar(v, sistema, usuario, fotos, temp):
    conteudo = [{"type": "text", "text": usuario},
                *[{"type": "image_url", "image_url": {"url": _foto_para_url(f), "detail": v["detail"]}}
                  for f in fotos[: v["n"]]]]
    kw = dict(model=v["model"], messages=[{"role": "system", "content": sistema},
                                          {"role": "user", "content": conteudo}],
              response_format={"type": "json_object"}, max_tokens=6000, temperature=temp)
    if v.get("extra"):
        kw["extra_body"] = v["extra"]
    for t in range(3):
        try:
            r = CLI.chat.completions.create(**kw)
            txt = (r.choices[0].message.content or "").strip()
            i, j = txt.find("{"), txt.rfind("}")
            return json.loads(txt[i:j + 1]), r.usage
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 * (t + 1))
    return {"erro": str(err)[:200]}, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    votos = int(sys.argv[sys.argv.index("--votos") + 1]) if "--votos" in sys.argv else 1
    so_ids = set(sys.argv[sys.argv.index("--ids") + 1].split(",")) if "--ids" in sys.argv else None
    if votos > 1:
        args = [a for a in args if a != str(votos)]
    if so_ids:
        args = [a for a in args if a != sys.argv[sys.argv.index("--ids") + 1]]
    mod = __import__(args[0], fromlist=["SISTEMA"])
    base = [it for it in itens() if it["_truth"].get("aparencia") in ("ok", "desbotado")]
    if so_ids:
        base = [it for it in base if str(it["id"]) in so_ids]
    print(f"{args[0]}: {len(base)} itens ({sum(it['_truth']['aparencia'] == 'desbotado' for it in base)} desbotados)")
    for nome in args[1:]:
        v = VAR[nome]
        t0 = time.time()

        def um(it):
            rs = [chamar(v, mod.SISTEMA, mod.usuario(it.get("titulo") or ""), it.get("fotos") or [],
                         0.1 if votos == 1 else 0.7) for _ in range(votos)]
            return it, rs

        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(um, base))
        tin = tout = 0
        linhas = []
        for it, rs in res:
            ds = [r.get("desbotado") for r, _ in rs]
            ms = [r.get("mancha") for r, _ in rs]
            for _, u in rs:
                if u:
                    tin += u.prompt_tokens
                    tout += u.completion_tokens
            n_sim = sum(d == "sim" for d in ds)
            n_tal = sum(d == "talvez" for d in ds)
            linhas.append({"id": str(it["id"]), "verdade": it["_truth"]["aparencia"], "sim": n_sim, "talvez": n_tal,
                           "mancha": sum(m == "sim" for m in ms), "votos": len(rs),
                           "sinais": [r.get("sinais_desbotado") for r, _ in rs][:1],
                           "mancha_onde": [r.get("mancha_onde") for r, _ in rs if r.get("mancha") == "sim"][:1]})
        pin, pout = PRECO[v["model"]]
        custo = tin / 1e6 * pin + tout / 1e6 * pout
        (SAIDA / f"estado_{args[0]}_{nome}_v{votos}.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=1))
        pos = [l for l in linhas if l["verdade"] == "desbotado"]
        neg = [l for l in linhas if l["verdade"] == "ok"]
        print(f"\n== {nome} ({votos} voto(s)) | custo ≈ US${custo:.3f} | {time.time() - t0:.0f}s")
        for regra, f in [("sim (maioria)", lambda l: l["sim"] * 2 > l["votos"]),
                         ("sim em algum voto", lambda l: l["sim"] > 0),
                         ("sim ou talvez", lambda l: l["sim"] + l["talvez"] > 0)]:
            tp = [l["id"] for l in pos if f(l)]
            fp = [l["id"] for l in neg if f(l)]
            print(f"  {regra:20} pega {len(tp)}/{len(pos)} {tp} | alarme falso {len(fp)}/{len(neg)} {fp}")
        mm = [(l["id"], l["mancha_onde"]) for l in linhas if l["mancha"] * 2 > l["votos"] or (l["votos"] == 1 and l["mancha"])]
        print(f"  mancha: {len(mm)} itens -> {mm[:12]}")


if __name__ == "__main__":
    main()
