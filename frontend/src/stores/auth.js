// Store di autenticazione. Stesso schema di admin/index.html (form OAuth2
// password su /api/auth/login, token in sessionStorage - non localStorage,
// cosi' il login non sopravvive alla chiusura della scheda: coerente con la
// nota di sicurezza gia' scritta per il pannello admin, questa pagina non ha
// una sua autenticazione aggiuntiva oltre al token JWT).
import { defineStore } from "pinia";
import { API_BASE } from "../api/client";

const STORAGE_KEY = "leank_spc_auth";

function loadStored() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = defineStore("auth", {
  state: () => {
    const stored = loadStored();
    return {
      accessToken: stored?.accessToken ?? null,
      refreshToken: stored?.refreshToken ?? null,
      username: stored?.username ?? null,
    };
  },
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    initials: (state) => (state.username ? state.username.slice(0, 2).toUpperCase() : "?"),
  },
  actions: {
    persist() {
      try {
        sessionStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ accessToken: this.accessToken, refreshToken: this.refreshToken, username: this.username })
        );
      } catch {
        // sessionStorage non disponibile (es. modalita' privata restrittiva): il
        // login resta valido solo in memoria per la sessione corrente della pagina.
      }
    },
    async login(username, password) {
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      const res = await fetch(API_BASE + "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Credenziali non valide.");
      }
      const data = await res.json();
      this.accessToken = data.access_token;
      this.refreshToken = data.refresh_token;
      this.username = username;
      this.persist();
    },
    async tryRefresh() {
      if (!this.refreshToken) return false;
      try {
        const res = await fetch(API_BASE + "/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        this.persist();
        return true;
      } catch {
        return false;
      }
    },
    logout() {
      this.accessToken = null;
      this.refreshToken = null;
      this.username = null;
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // vedi nota in persist()
      }
    },
  },
});
