// Fetch wrapper condiviso da tutti i moduli in api/*.js. Stesso pattern gia'
// collaudato in admin/index.html (token Bearer, sessionStorage) - qui in piu'
// c'e' il refresh automatico su 401 (un solo tentativo) prima di forzare
// il logout, per non buttare fuori l'operatore mentre e' a meta' di un Run
// solo perche' l'access token e' scaduto (30 minuti di default).

import { useAuthStore } from "../stores/auth";

// In produzione (dopo "npm run build") il frontend e' servito dallo stesso
// backend FastAPI: stessa origine, nessuna base URL da configurare. In
// sviluppo (npm run dev, porta 5173) serve puntare al backend separato.
const DEV_DEFAULT_BASE = "http://127.0.0.1:8000";
export const API_BASE = import.meta.env.DEV
  ? (import.meta.env.VITE_API_BASE_URL || DEV_DEFAULT_BASE)
  : "";

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, params, isRetry = false } = {}) {
  const auth = useAuthStore();
  let url = API_BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }

  const headers = { "Content-Type": "application/json" };
  if (auth.accessToken) headers.Authorization = "Bearer " + auth.accessToken;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !isRetry && auth.refreshToken) {
    const refreshed = await auth.tryRefresh();
    if (refreshed) return request(path, { method, body, params, isRetry: true });
    auth.logout();
    throw new ApiError(401, "Sessione scaduta, effettua di nuovo il login.");
  }

  if (res.status === 204) return null;

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
  }
  return data;
}

export const api = {
  get: (path, params) => request(path, { method: "GET", params }),
  post: (path, body, params) => request(path, { method: "POST", body, params }),
  put: (path, body, params) => request(path, { method: "PUT", body, params }),
  delete: (path, params) => request(path, { method: "DELETE", params }),
};
