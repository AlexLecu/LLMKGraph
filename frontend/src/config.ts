// Central place for every backend URL the UI talks to.
// Override via Vite env vars (see .env.example); defaults match the local setup.
const env = import.meta.env;

const trim = (url: string) => url.replace(/\/+$/, '');

export const API_URL = trim(env.VITE_API_URL ?? 'http://localhost:5555');
export const GRAPHDB_URL = trim(env.VITE_GRAPHDB_URL ?? 'http://localhost:7200');
export const CHAT_URL = env.VITE_CHAT_URL ?? 'http://localhost:8000/';
export const EVAL_URL =
  env.VITE_EVAL_URL ?? 'http://localhost:8502/?embed=true&embed_options=show_toolbar';
