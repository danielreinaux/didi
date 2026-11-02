#!/usr/bin/env bash
# Roda a cada 15 min (didi-atualizar.timer): se o main mudou src/, requirements.txt ou deploy/,
# baixa o código novo e roda o setup.sh (instala o que faltar e reinicia o robô).
# Os commits de dados dos crons não mexem nessas pastas → não reiniciam nada.
set -euo pipefail
cd /opt/didi
git fetch -q --depth 1 origin main
for p in src requirements.txt deploy; do
  if [ "$(git rev-parse "HEAD:$p")" != "$(git rev-parse "origin/main:$p")" ]; then
    echo "mudou $p — atualizando"
    git reset -q --hard origin/main   # antes do exec: o bash não pode ler um setup.sh que muda no meio
    exec bash deploy/vps/setup.sh
  fi
done
