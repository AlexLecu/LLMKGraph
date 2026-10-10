# Deploying LLMKGraph for free

The project has four moving parts with very different hosting needs:

| Component | Folder | Needs | Free option |
|---|---|---|---|
| Vue frontend | `frontend/` | static files | **GitHub Pages** (workflow included) |
| Chainlit chatbot | `backend/weaviate_rag/` | Python, Weaviate, an LLM | **Hugging Face Spaces** (Docker) + Groq/Gemini free API + Weaviate Cloud sandbox |
| Flask API + Streamlit | `backend/` | Python, Java, GraphDB | **Oracle Cloud Always Free VM** (or any VPS) with `docker-compose` |
| GraphDB | docker image | ~2 GB RAM Java server | same VM as above |

There is no serverless free tier that runs GraphDB or local Ollama models, so a
100 % free deployment means: static frontend on Pages, chatbot on a Space with a
hosted LLM API, and the GraphDB-backed API either on a free VM or left local.

---

## 1. Frontend on GitHub Pages (5 minutes)

Already wired up in `.github/workflows/deploy-frontend.yml`.

1. GitHub repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Optional: **Settings → Secrets and variables → Actions → Variables**, add
   `VITE_API_URL`, `VITE_GRAPHDB_URL`, `VITE_CHAT_URL`, `VITE_EVAL_URL` pointing at
   wherever you deploy the other parts (see below). Without them the UI builds but
   talks to `localhost`.
3. Push to `main` (or run the workflow manually). The site appears at
   `https://<user>.github.io/LLMKGraph/`.

The build uses `VITE_BASE_PATH=/LLMKGraph/` so assets and the router work under
the sub-path; `404.html` is a copy of `index.html` so `/chat` deep links work.

## 2. Chatbot on Hugging Face Spaces (free CPU, 16 GB RAM)

### 2a. Pick a hosted LLM (free tiers)

The chatbot no longer requires Ollama. Set `CHAT_PROVIDER=openai-compatible` and
point it at any OpenAI-style endpoint:

| Provider | `CHAT_API_BASE_URL` | Example `CHAT_MODELS` |
|---|---|---|
| Groq (fast, generous free tier) | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile,deepseek-r1-distill-llama-70b` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` |
| OpenRouter (free models end in `:free`) | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct:free` |

Models containing `deepseek-r1` get the "thinking" step UI automatically.

### 2b. Pick a Weaviate

* **Weaviate Cloud sandbox** (free, expires after 14 days, fine for demos):
  create a cluster at <https://console.weaviate.cloud>, then set
  `WEAVIATE_URL` and `WEAVIATE_API_KEY`. Ingest the data once from your machine
  with the same two env vars: `python ingest_data.py` in `backend/weaviate_rag`.
* **Embedded Weaviate** inside the Space (`WEAVIATE_MODE=embedded`): no external
  service, but the free Space disk is ephemeral, so you must run
  `create_schema.py` + `ingest_data.py` at container start (add them to the
  `CMD`). Only worth it if the sandbox expiry bothers you.

### 2c. Create the Space

1. <https://huggingface.co/new-space> → SDK **Docker**, hardware **CPU basic (free)**.
2. The Space repo must have `Dockerfile` at its root, so push the contents of
   `backend/` and rename the chatbot Dockerfile:

   ```bash
   git clone https://huggingface.co/spaces/<user>/<space> hf-space
   rsync -a --exclude '__pycache__' --exclude '*.rdf' --exclude evaluation backend/ hf-space/
   cp backend/weaviate_rag/Dockerfile hf-space/Dockerfile
   cd hf-space && git add -A && git commit -m "Deploy chatbot" && git push
   ```

   The Dockerfile already listens on port **7860** (what Spaces expects) and runs
   Chainlit headless.
3. **Settings → Variables and secrets** on the Space:
   `CHAT_PROVIDER`, `CHAT_API_BASE_URL`, `CHAT_MODELS` as variables;
   `CHAT_API_KEY`, `WEAVIATE_URL`, `WEAVIATE_API_KEY` as secrets.
4. The chatbot is served at `https://<user>-<space>.hf.space/`. Put that URL in the
   `VITE_CHAT_URL` GitHub variable so the frontend's Chat tab embeds it.

Free Spaces go to sleep after 48 h without traffic and wake on the first request.

## 3. Flask API + GraphDB (the part that needs a real machine)

GraphDB is a Java server that wants ~2 GB RAM, which rules out the 512 MB
"free web service" tiers (Render, Railway trial, Fly). Options, cheapest first:

1. **Oracle Cloud Always Free** – an ARM VM with 4 OCPU / 24 GB RAM at no cost
   (credit card required for sign-up, never charged on the free shapes). Install
   Docker, clone the repo, copy `.env.example` → `.env`, then:

   ```bash
   CORS_ORIGINS=https://<user>.github.io docker compose up -d --build
   ```

   Then import `data/amd_repo.rdf` into a GraphDB repository called `amd_repo`
   at `http://<vm-ip>:7200` (Workbench → Import). Put a reverse proxy with HTTPS
   in front (Caddy does it in two lines) because GitHub Pages is HTTPS and
   browsers block mixed content. Set `VITE_API_URL` / `VITE_GRAPHDB_URL` to the
   proxied URLs.
2. **Any student / free-credit VPS** (GitHub Student Pack: DigitalOcean / Azure
   credits) – same `docker compose` recipe.
3. **Run the API locally** and only publish the frontend + chatbot. The Home tab
   will then only work from your machine; the Chat tab works for everyone.

The Streamlit evaluation app (`backend/streamlit/`) has the same GraphDB
dependency, so it lives on the same VM (port 8502) or on
<https://share.streamlit.io> if GraphDB is reachable over the internet.

## Updating the self-hosted chatbot (current setup)

The chatbot has so far been served from a machine of your own: the
`amd-chatbot` container (built from `backend/weaviate_rag/docker-compose.yml`),
with Weaviate from `docker-compose-weaviate.yml` and Ollama running on the host.
To roll out new code there without touching the data:

```bash
cd LLMKGraph
bash backend/weaviate_rag/update.sh     # git pull, rebuild image, restart container
```

Only the chatbot image is rebuilt; the Weaviate volume and the Ollama models stay
as they are. Two things to know:

* `docker-compose-weaviate.yml` keeps its data in an **anonymous** Docker volume.
  Never run `docker compose -f docker-compose-weaviate.yml down -v` on that
  machine, and back the volume up before upgrading Weaviate
  (`docker run --rm -v <volume>:/d -v $PWD:/b alpine tar czf /b/weaviate-backup.tgz /d`).
* The build context is `backend/`; `backend/.dockerignore` keeps the research
  artefacts (evaluation notebooks, extracted relations, scripts) out of the image.

## Security checklist before exposing anything

* Never commit `.env` (it is git-ignored now); use `.env.example` as the template.
* Set `CORS_ORIGINS` to your Pages origin instead of `*`.
* Keep `FLASK_DEBUG=0` (debug mode exposes a remote code execution console).
* Protect GraphDB (enable security in Workbench → Setup → Users and Access) if its
  port is reachable from the internet; the frontend queries it directly.
* Dependabot now watches `backend/`, `backend/weaviate_rag/`, `frontend/` and the
  Dockerfiles; merge its PRs regularly.
