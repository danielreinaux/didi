#!/usr/bin/env bash
# Prepara a VPS (Ubuntu 24.04) para o robô do Didi. Rodar como root:  bash deploy/vps/setup.sh
# Idempotente: dá pra rodar de novo para atualizar o código e reiniciar o serviço.
# As chaves vêm em /root/didi.env (o criar_vps.py manda) ou já em /opt/didi/.env.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
timedatectl set-timezone UTC || true
apt-get update -y
apt-get install -y python3-venv python3-pip git ufw
ufw allow OpenSSH >/dev/null && ufw --force enable >/dev/null
id didi >/dev/null 2>&1 || useradd -m -s /bin/bash didi
# o repo é do usuário didi; o root (setup/atualizador) também mexe nele
git config --system --get-all safe.directory 2>/dev/null | grep -qx /opt/didi || git config --system --add safe.directory /opt/didi

if [ ! -d /opt/didi/.git ]; then
  git clone --depth 1 --filter=blob:none --sparse https://github.com/danielreinaux/didi.git /opt/didi
  git -C /opt/didi sparse-checkout set --no-cone '/src/' '/requirements.txt' '/deploy/'
else
  git -C /opt/didi fetch --depth 1 origin main && git -C /opt/didi reset --hard origin/main
fi
cd /opt/didi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -U pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install-deps chromium >/dev/null
[ -f /root/didi.env ] && mv /root/didi.env /opt/didi/.env
[ -f /opt/didi/.env ] || { echo "falta /opt/didi/.env (OPENAI_API_KEY, OPENROUTER_API_KEY)"; exit 1; }
chown -R didi:didi /opt/didi
chmod 600 /opt/didi/.env
sudo -u didi /opt/didi/.venv/bin/playwright install chromium
cp deploy/vps/didi-sombra.service deploy/vps/didi-atualizar.service deploy/vps/didi-atualizar.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable didi-sombra >/dev/null
systemctl enable --now didi-atualizar.timer >/dev/null
systemctl restart didi-sombra
sleep 5 && systemctl --no-pager --lines=5 status didi-sombra
