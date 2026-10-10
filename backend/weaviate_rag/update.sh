#!/usr/bin/env bash
# Update the self-hosted AMD chatbot to the latest code on the current branch.
# Run on the machine that serves it:  bash backend/weaviate_rag/update.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== pulling latest code"
git pull --ff-only

echo "== rebuilding chatbot image (Weaviate and Ollama are untouched)"
docker compose build chatbot

echo "== restarting container"
docker compose up -d chatbot

echo "== removing dangling images from previous builds"
docker image prune -f >/dev/null

echo "== status"
docker compose ps
echo "Chatbot logs: docker compose logs -f chatbot"
