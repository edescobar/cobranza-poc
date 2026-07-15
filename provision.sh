#!/usr/bin/env bash
# One-shot provisioner for a fresh Ubuntu 24.04 droplet.
# Run from the DigitalOcean web console (already root):
#   curl -fsSL https://raw.githubusercontent.com/edescobar/cobranza-poc/main/provision.sh | bash
set -x
export DEBIAN_FRONTEND=noninteractive

apt-get update -y && apt-get install -y git curl
command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh

rm -rf /root/cobranza-poc
git clone https://github.com/edescobar/cobranza-poc.git /root/cobranza-poc
cd /root/cobranza-poc

printf 'POSTGRES_PASSWORD=cobranza-poc-local\nOLLAMA_MODEL=qwen2.5:3b\n' > .env

docker compose up -d postgres api ollama
echo ">>> waiting for ollama to come up..."; sleep 15
# qwen2.5-instruct: no reasoning mode, answers directly (fast). Qwen3 reasons even with think:false.
docker compose exec -T ollama ollama pull qwen2.5:3b </dev/null   # </dev/null so curl|bash doesn't eat the rest of the script
docker compose exec -T postgres psql -U cobranza -d cobranza < db/seed_sample.sql
sleep 5

echo "=================================================="
echo ">>> HEALTH:"
curl -s localhost:8000/health; echo
echo ">>> PATTERNS ON  (should offer a payment plan):"
curl -s localhost:8000/reply -H 'content-type: application/json' \
  -d '{"text":"No tengo plata este mes","patterns":true}'; echo
echo ">>> PATTERNS OFF (plainer reply):"
curl -s localhost:8000/reply -H 'content-type: application/json' \
  -d '{"text":"No tengo plata este mes","patterns":false}'; echo
echo "=================================================="
echo ">>> DONE. Open  http://45.55.83.61:8000  in your browser."
