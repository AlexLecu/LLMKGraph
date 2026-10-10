#!/usr/bin/env bash
# Boot sequence for the Space: Weaviate -> schema + data -> Chainlit.
set -euo pipefail
cd /app/backend/weaviate_rag

export PERSISTENCE_DATA_PATH=${PERSISTENCE_DATA_PATH:-/data/weaviate}
export AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
export DEFAULT_VECTORIZER_MODULE=none
export ENABLE_MODULES=
export CLUSTER_HOSTNAME=node1
export QUERY_DEFAULTS_LIMIT=25
export DISABLE_TELEMETRY=true
mkdir -p "$PERSISTENCE_DATA_PATH"

echo "== starting Weaviate"
weaviate --host 127.0.0.1 --port 8080 --scheme http > /tmp/weaviate.log 2>&1 &
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/v1/.well-known/ready > /dev/null && break
  sleep 1
done
curl -sf http://127.0.0.1:8080/v1/.well-known/ready > /dev/null || { echo "Weaviate did not start"; tail -50 /tmp/weaviate.log; exit 1; }

echo "== loading the knowledge graph (schema + relations)"
python create_schema.py
python ingest_from_json.py /app/backend/data/Deepseek_V3_Relations_ct.json /app/backend/data/Deepseek_V3_Relations_pubs.json

echo "== starting Chainlit on port ${PORT:-7860}"
exec chainlit run chatbot.py --host 0.0.0.0 --port "${PORT:-7860}" --headless
