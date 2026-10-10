# Deploying LLMKGraph for free

The project has four moving parts with very different hosting needs:

| Component | Folder | Needs | Free option |
|---|---|---|---|
| Vue frontend | `frontend/` | static files | **GitHub Pages** (workflow included) |
| Chainlit chatbot | `backend/weaviate_rag/` | Python, Weaviate, an LLM | **Render** free web service (single container, Weaviate bundled) + Gemini free API |
| Flask API + Streamlit | `backend/` | Python, Java, GraphDB | **Oracle Cloud Always Free VM** (or any VPS) with `docker-compose` |
| GraphDB | docker image | ~2 GB RAM Java server | same VM as above |

There is no serverless free tier that runs GraphDB or local Ollama models, so a
100 % free deployment means: static frontend on Pages, chatbot in one free
container on Render with a hosted LLM API, and the GraphDB-backed API either on a
free VM or left local.

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

## 2. Chatbot on Render (free web service)

> Hugging Face Docker Spaces now require a PRO subscription, so the chatbot
> goes to [Render](https://render.com): free plan, 512 MB RAM, Docker, no card.
> The service sleeps after 15 minutes without traffic and wakes on the first
> request (about a minute). Fine for a demo.

Everything is in the repository: [`deploy/chatbot/Dockerfile`](deploy/chatbot/Dockerfile)
(Weaviate binary + Chainlit, knowledge graph loaded from JSON at start-up, ~10 s)
and the blueprint [`render.yaml`](render.yaml).

1. Render dashboard → **New → Blueprint** → connect the GitHub repository.
   Render reads `render.yaml` and asks for the one secret, `CHAT_API_KEY`
   (a Gemini API key; the blueprint already points at Gemini's OpenAI-compatible
   endpoint and the `gemini-3.8-flash` / `gemini-3.1-flash-lite` models).
2. Deploy. The service URL looks like `https://llmkgraph-amd-chat.onrender.com`.
3. Put that URL in the GitHub Actions variable `VITE_CHAT_URL` and re-run the
   Pages workflow, so the Chat tab of the published frontend embeds it.

To use another OpenAI-compatible provider, change `CHAT_API_BASE_URL`,
`CHAT_MODELS` and the key in the Render dashboard (Environment tab).

The shipped data is `data/Extracted_Relations/2025-03-12/Deepseek_V3_Relations_ct.json`
(100 AMD clinical trials). To ship a different set, point the `COPY` line in the
Dockerfile at another relations JSON in the repository.

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
