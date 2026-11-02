"""Cria (ou reaproveita) a VPS do Didi na Hetzner e instala o robô sombra — tudo por API.

Único passo manual: conta na Hetzner + token de API (Security → API tokens, "Read & Write")
salvo como HCLOUD_TOKEN no .env do didi. O resto é aqui: cadastra a chave SSH ~/.ssh/didi_vps,
escolhe o servidor x86 mais barato com 2 vCPU/4 GB (Nuremberg → Falkenstein → Helsinki), cria,
espera o SSH, manda só OPENAI_API_KEY/OPENROUTER_API_KEY (sem SMTP: o sombra não manda e-mail)
e roda o setup.sh. Rodar de novo é seguro: reaproveita a chave e o servidor que já existirem.

Uso (na raiz do repo):  python3 deploy/vps/criar_vps.py   (DIDI_ENV=<caminho> se o .env estiver em outro lugar)
Python local sem SSL confiável → as chamadas à API vão pelo curl.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

API = "https://api.hetzner.cloud/v1"
NOME = "didi-radar"
CHAVE = Path.home() / ".ssh" / "didi_vps"
KNOWN = Path.home() / ".ssh" / "didi_vps_known_hosts"
LOCAIS = ["nbg1", "fsn1", "hel1"]
CHAVES_ENV = ("OPENAI_API_KEY", "OPENROUTER_API_KEY")
AQUI = Path(__file__).resolve().parent


def ler_env() -> dict:
    env = {}
    arq = Path(os.environ.get("DIDI_ENV", AQUI.parent.parent / ".env"))
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            k, v = linha.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = ler_env()
TOKEN = ENV.get("HCLOUD_TOKEN")


def api(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    # token vai pelo stdin (-H @-), não fica visível na lista de processos
    cmd = ["curl", "-sS", "-X", metodo, "-H", "@-", "-H", "Content-Type: application/json", API + caminho]
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        if corpo is not None:
            json.dump(corpo, f)
            f.flush()
            cmd[-1:-1] = ["--data-binary", "@" + f.name]
        r = subprocess.run(cmd, input=f"Authorization: Bearer {TOKEN}\n", capture_output=True, text=True, check=True)
    resp = json.loads(r.stdout or "{}")
    if "error" in resp:
        raise RuntimeError(f"{metodo} {caminho}: {resp['error'].get('code')} — {resp['error'].get('message')}")
    return resp


def chave_ssh() -> int:
    pub = (CHAVE.with_suffix(".pub")).read_text().strip()
    for k in api("GET", "/ssh_keys?per_page=50")["ssh_keys"]:
        if k["public_key"].split()[:2] == pub.split()[:2]:
            return k["id"]
    return api("POST", "/ssh_keys", {"name": "didi-vps", "public_key": pub})["ssh_key"]["id"]


def opcoes() -> list[tuple[float, str, str]]:
    """(preço mensal, tipo, local) dos x86 atuais com ≥2 vCPU e ≥4 GB, do mais barato pro mais caro."""
    out = []
    for t in api("GET", "/server_types?per_page=50")["server_types"]:
        if t.get("deprecation") or t.get("deprecated") or t.get("architecture") != "x86":
            continue
        if t["cores"] < 2 or t["memory"] < 4:
            continue
        for p in t["prices"]:
            if p["location"] in LOCAIS:
                out.append((float(p["price_monthly"]["gross"]), t["name"], p["location"]))
    return sorted(out, key=lambda o: (o[0], LOCAIS.index(o[2])))


def servidor(chave_id: int) -> dict:
    achados = api("GET", f"/servers?name={NOME}")["servers"]
    if achados:
        print(f"servidor {NOME} já existe — reaproveitando")
        return achados[0]
    for preco, tipo, local in opcoes():
        try:
            s = api("POST", "/servers", {"name": NOME, "server_type": tipo, "image": "ubuntu-24.04",
                                         "location": local, "ssh_keys": [chave_id], "labels": {"app": "didi"}})
            print(f"criado {NOME}: {tipo} em {local} (≈€{preco:.2f}/mês)")
            return s["server"]
        except RuntimeError as e:
            print(f"  {tipo}/{local} indisponível ({e}) — tentando o próximo")
    sys.exit("nenhum tipo de servidor disponível")


def ssh(ip: str, comando: str, entrada: str | None = None, checar: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["ssh", "-i", str(CHAVE), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                           "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={KNOWN}",
                           f"root@{ip}", comando], input=entrada, text=True, check=checar)


def main() -> None:
    if not TOKEN:
        sys.exit("falta HCLOUD_TOKEN no .env (Hetzner Console → projeto → Security → API tokens → Read & Write)")
    faltam = [k for k in CHAVES_ENV if not ENV.get(k)]
    if faltam:
        sys.exit(f"faltam no .env: {', '.join(faltam)}")
    s = servidor(chave_ssh())
    for _ in range(60):
        if s["status"] == "running":
            break
        time.sleep(5)
        s = api("GET", f"/servers/{s['id']}")["server"]
    ip = s["public_net"]["ipv4"]["ip"]
    print(f"IP: {ip} — esperando o SSH…")
    for _ in range(40):
        if ssh(ip, "true", checar=False).returncode == 0:
            break
        time.sleep(5)
    else:
        sys.exit("SSH não respondeu")
    env = "".join(f"{k}={ENV[k]}\n" for k in CHAVES_ENV)
    ssh(ip, "umask 077 && cat > /root/didi.env", entrada=env)
    ssh(ip, "cat > /root/setup.sh", entrada=(AQUI / "setup.sh").read_text())
    ssh(ip, "bash /root/setup.sh")
    print(f"\npronto. Logs:  ssh -i ~/.ssh/didi_vps root@{ip} journalctl -u didi-sombra -f")


if __name__ == "__main__":
    main()
