# Read-only API for the public demo: Flask + an in-process rdflib triplestore
# loaded from the relation JSON files in the repository (no GraphDB, no Java).
# Build context is the repository root:
#   docker build -f deploy/api/Dockerfile -t llmkgraph-api .
FROM python:3.11-slim

WORKDIR /app
COPY deploy/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app.py backend/search_kg.py backend/embedded_store.py backend/enrich_kg_gpt.py \
     backend/bulk_relations.py backend/prompts.py /app/
COPY backend/disambiguation /app/disambiguation
COPY data/CausalAMD_ont.rdf /app/data/CausalAMD_ont.rdf
COPY data/Extracted_Relations/2025-03-12/Deepseek_V3_Relations_ct.json \
     data/Extracted_Relations/2025-03-12/Deepseek_V3_Relations_pubs.json /app/data/

ENV PYTHONUNBUFFERED=1 \
    PORT=5555 \
    EMBEDDED_STORE=1 \
    EMBEDDED_BASE_DIR=/app \
    EMBEDDED_REPOS='[{"id":"amd_clinical_trials","ontology":"data/CausalAMD_ont.rdf","relations":["data/Deepseek_V3_Relations_ct.json"]},{"id":"amd_abstracts","ontology":"data/CausalAMD_ont.rdf","relations":["data/Deepseek_V3_Relations_pubs.json"]}]' \
    READ_ONLY=1 \
    FLASK_DEBUG=0

# The API queries its own embedded store over HTTP, so one worker with threads.
CMD ["sh", "-c", "export GRAPHDB_URL=http://127.0.0.1:${PORT}; exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 120 app:app"]
