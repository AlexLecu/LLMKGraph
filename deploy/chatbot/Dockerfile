# Self-contained AMD chatbot for a single free container (Render, Koyeb, Fly, ...):
# Weaviate (single binary, BM25 only) + Chainlit UI; the knowledge graph is
# loaded from JSON at start-up (~10 s), so no external database is needed.
#
# Build context is the repository root:
#   docker build -f deploy/chatbot/Dockerfile -t llmkgraph-chat .
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ARG WEAVIATE_VERSION=1.28.2
ARG TARGETARCH=amd64
RUN curl -fsSL "https://github.com/weaviate/weaviate/releases/download/v${WEAVIATE_VERSION}/weaviate-v${WEAVIATE_VERSION}-linux-${TARGETARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin weaviate && chmod +x /usr/local/bin/weaviate

WORKDIR /app
COPY backend/weaviate_rag/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    python -m spacy download en_core_web_sm

COPY backend/prompts.py /app/backend/prompts.py
COPY backend/disambiguation /app/backend/disambiguation
COPY backend/weaviate_rag /app/backend/weaviate_rag
COPY deploy/chatbot/start.sh /app/backend/start.sh
# Relations shipped with the repository (100 AMD clinical trials, DeepSeek V3 extraction)
COPY data/Extracted_Relations/2025-03-12/Deepseek_V3_Relations_ct.json /app/backend/data/all_relations.json

WORKDIR /app/backend/weaviate_rag
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/backend \
    PORT=7860 \
    WEAVIATE_HOST=localhost \
    WEAVIATE_HTTP_PORT=8080 \
    WEAVIATE_GRPC_PORT=50051 \
    WEAVIATE_VECTORIZER=none
EXPOSE 7860

CMD ["bash", "/app/backend/start.sh"]
