// Central place for every backend URL the UI talks to.
// Override via Vite env vars (see .env.example); defaults match the local setup.
const env = import.meta.env;

// An env var that is set but empty (e.g. an unset GitHub Actions variable)
// must fall back to the default just like a missing one.
const pick = (value: string | undefined, fallback: string) =>
  value && value.trim() ? value.trim() : fallback;
const trim = (url: string) => url.replace(/\/+$/, '');

export const API_URL = trim(pick(env.VITE_API_URL, 'http://localhost:5555'));
export const GRAPHDB_URL = trim(pick(env.VITE_GRAPHDB_URL, 'http://localhost:7200'));
// Chat: the native page talks to the chat API (backend/weaviate_rag/chat_api.py, same
// origin as the API behind the server's nginx). VITE_CHAT_EMBED_URL instead embeds
// a Chainlit UI in an iframe (e.g. the Render demo).
export const CHAT_API_URL = trim(pick(env.VITE_CHAT_API_URL, API_URL));
export const CHAT_EMBED_URL = (env.VITE_CHAT_EMBED_URL ?? '').trim();
// Repository shown first when several exist (falls back to the first AMD one).
export const DEFAULT_REPO = pick(env.VITE_DEFAULT_REPO, 'amd_repo_mistral');
