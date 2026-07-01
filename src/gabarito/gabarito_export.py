"""Puxa o gabarito (a 'verdade' que o stakeholder preencheu) do Redis via API.

As respostas do gabarito vivem no Upstash (chaves gabarito:<id>), expostas pela
rota /api/gabarito da votacao. Aqui só fazemos um GET e salvamos local pra o
diff usar — não precisa das credenciais do Redis (a API já resolve isso).

Uso:
  python -m src.gabarito.gabarito_export
  python -m src.gabarito.gabarito_export --url https://votacao-two.vercel.app/api/gabarito
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REG = ROOT / "data" / "regressao"
OUT = REG / "gabarito_respostas.json"
URL_PADRAO = "https://votacao-two.vercel.app/api/gabarito"


def _arg(nome: str, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main() -> None:
    url = _arg("--url", URL_PADRAO)
    REG.mkdir(parents=True, exist_ok=True)
    print(f"Puxando gabarito de {url} …")
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Falha ao puxar: {e}")
        sys.exit(1)

    # Formato esperado: { "<id>": { criterio: valor, ... }, ... }
    if not isinstance(data, dict):
        print("Resposta inesperada da API (não é um objeto).")
        sys.exit(1)

    preenchidos = sum(1 for v in data.values() if isinstance(v, dict) and v)
    doc = {
        "puxado_em": datetime.now(timezone.utc).isoformat(),
        "origem": url,
        "respostas": data,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK -> {OUT}")
    print(f"  {len(data)} itens no gabarito · {preenchidos} com pelo menos 1 critério preenchido")
    if preenchidos == 0:
        print("  ⚠ Ninguém preencheu ainda — o diff não terá o que comparar.")


if __name__ == "__main__":
    main()
