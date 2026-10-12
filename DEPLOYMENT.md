# Deploying LLMKGraph

The public instance runs at **<https://llmkgraph.utcluj.ro>** on a server of the
Technical University of Cluj-Napoca (CloudUT). Everything it needs is in
[`deploy/server/`](deploy/server/): one `docker compose` project behind the
server's nginx, with the university reverse proxy in front for HTTPS.

```
browser ──HTTPS──▶ university reverse proxy (TLS) ──HTTP──▶ host nginx :80
                                                             │  Host: llmkgraph.utcluj.ro
                                                             ▼
                                         llmkgraph-web  (127.0.0.1:3002)
                                         nginx: Vue UI + same-origin proxy
                                            │ /api/chat          │ /api/*
                                            ▼                    ▼
                                   llmkgraph-chatbot      llmkgraph-api ──▶ llmkgraph-graphdb
                                   Weaviate + chat API    Flask (Gunicorn)    GraphDB 10.8
                                            │
                                            └──▶ Groq (OpenAI-compatible LLM API)
```

| Container | Image source | Role |
|---|---|---|
| `llmkgraph-web` | [`deploy/server/web.Dockerfile`](deploy/server/web.Dockerfile) | Built Vue UI + nginx routing `/api/chat` and `/api/*` |
| `llmkgraph-api` | [`backend/Dockerfile`](backend/Dockerfile) | Flask API: graph search, SPARQL proxy, `/api/evaluation`, extraction, edits |
| `llmkgraph-chatbot` | [`deploy/chatbot/Dockerfile`](deploy/chatbot/Dockerfile) | Weaviate (BM25) with the graph baked in at build time + the streaming chat API |
| `llmkgraph-graphdb` | `ontotext/graphdb:10.8.0` | The six AMD repositories (named volume `graphdb-data`) |

Only `llmkgraph-web` is published, and only on `127.0.0.1`; GraphDB's Workbench
is on `127.0.0.1:7201` for administration through an SSH tunnel. The project does
not share containers, volumes or ports with other applications on the same server.

## What the public site allows

The API runs with `READ_ONLY=1`:

* **Everyone** can browse and search every graph, use the chat and the LLM-comparison page.
* **Extraction from a pasted abstract** uses one model only (`EXTRACTION_MODEL`,
  Groq `openai/gpt-oss-120b`) and is rate limited per visitor (about 20 per hour).
* **Adding, deleting and the reasoner** work only in the repositories listed in
  `WRITABLE_REPOS` (the empty `amd_playground` graph). The thesis graphs answer 403.
* Batch extraction with the fine-tuned models is disabled (it needs the OpenAI,
  Mistral and DeepSeek keys); run the project locally for that.

Groq is pay-as-you-go: set a monthly **spend limit** in the Groq console
(Billing → Spend Limits). A chat question costs about $0.001, an extraction about $0.002.

## Repositories

[`deploy/server/load_graphdb.py`](deploy/server/load_graphdb.py) creates and fills
them from the public files in [`data/Extracted_Relations/`](data/Extracted_Relations/),
with the CausalAMD ontology and the same cleaning as the upload path:

| Id | Shown as | Source |
|---|---|---|
| `amd_abstracts` | PubMed abstracts | DeepSeek V3, 999 abstracts |
| `amd_clinical_trials` | Clinical trials | DeepSeek V3, 100 clinical trials |
| `amd_repo_gpt_35` | GPT-3.5 Turbo (FT) | LLM comparison, 100 abstracts |
| `amd_repo_mistral` | Mistral Nemo (FT) | LLM comparison, 100 abstracts |
| `amd_repo_gpt_4o1_mini` | GPT-4o-mini | LLM comparison, 100 abstracts |
| `amd_playground` | Playground | empty, writable by visitors |

The chatbot's Weaviate holds the two DeepSeek sets (12,245 relations after cleaning).

## Installing on a server

Requirements: Docker with the compose plugin, nginx on the host, ~4 GB RAM free.

```bash
git clone https://github.com/AlexLecu/LLMKGraph.git && cd LLMKGraph/deploy/server
cp .env.example .env          # set GROQ_API_KEY and PUBLIC_URL (.env is git-ignored)
docker compose up -d --build  # first build takes a few minutes
docker compose run --rm load  # once: create and fill the GraphDB repositories
```

Then the host nginx site (needs sudo):

```bash
sudo cp nginx-host.conf /etc/nginx/sites-available/llmkgraph
sudo ln -s /etc/nginx/sites-available/llmkgraph /etc/nginx/sites-enabled/llmkgraph
sudo nginx -t && sudo systemctl reload nginx
```

The host block listens on ports 80 and 3000 (the ones the university proxy uses)
and matches only `server_name llmkgraph.utcluj.ro`, so other sites on the server are
not affected. TLS is terminated by the university proxy; do not add certificates locally.

## Updating

```bash
cd ~/LLMKGraph && git pull && cd deploy/server && docker compose up -d --build
```

The GraphDB volume is kept. `load_graphdb.py` skips repositories that already hold
relations, so it is safe to re-run after adding a new one.

## Things to know about the university proxy

* It does **not forward WebSockets**. That is why the chat and the comparison page
  are plain HTTP (streamed text and JSON) instead of Chainlit and Streamlit, which
  need WebSockets. Long requests and streaming responses work.
* While connected to the CloudUT VPN, its DNS (10.20.1.99) does not resolve the
  public subdomains; disconnect the VPN to open the site from the same machine.

## Running locally

See the Quick start in the [README](README.md#-quick-start): `docker compose up`
at the repository root starts GraphDB, the writable API, the Streamlit comparison
app and the frontend; the chatbot has its own stack in
[`backend/weaviate_rag/`](backend/weaviate_rag/) (Chainlit UI by default, or
`CHAT_UI=api` for the web chat page, with Ollama or any OpenAI-compatible API).

## Security checklist

* Never commit `.env`; use the `.env.example` templates.
* Keep `FLASK_DEBUG=0` (debug mode exposes a remote code execution console).
* Keep GraphDB unpublished (or bound to `127.0.0.1`), or enable its security
  (Workbench → Setup → Users and Access) before exposing it.
* Set a spend limit on every paid LLM key the public site uses.
* Dependabot watches the Python, npm, Docker and GitHub Actions manifests; merge its PRs regularly.
