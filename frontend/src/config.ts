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
export const CHAT_URL = pick(env.VITE_CHAT_URL, 'http://localhost:8000/');
export const EVAL_URL = pick(env.VITE_EVAL_URL, 'http://localhost:8502/?embed=true&embed_options=show_toolbar');
// Repository shown first when several exist (falls back to the first AMD one).
export const DEFAULT_REPO = pick(env.VITE_DEFAULT_REPO, 'amd_repo_mistral');
