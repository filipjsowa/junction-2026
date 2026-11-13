#!/usr/bin/env bash
# One-time setup on a fresh Hostinger VPS (Ubuntu), run as root:
#   curl -fsSL <raw URL of this file> | bash -s -- <git repo URL>
#   or, after cloning:  bash deploy/setup-vps.sh <git repo URL>
set -euo pipefail

REPO_URL="${1:?Usage: setup-vps.sh <git repo URL>}"
APP_DIR=/opt/swarm-detector

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
if ! command -v make >/dev/null || ! command -v git >/dev/null; then
  apt-get update && apt-get install -y make git
fi
if command -v ufw >/dev/null && ufw status | grep -q active; then
  ufw allow 80/tcp && ufw allow 443/tcp
fi

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  # Makes every docker compose / make command on the VPS use the prod setup (Caddy, no live reload).
  echo 'COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml' >> .env
fi

echo
echo "Next:"
echo "  1. nano $APP_DIR/.env   (passwords, API keys, DOMAIN=:80 for a first test over the IP)"
echo "  2. set VECTOR(...) in db/schema.sql to your embedding dimension"
echo "  3. cd $APP_DIR && make prod"
