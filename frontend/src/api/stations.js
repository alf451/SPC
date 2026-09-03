import { api } from "./client";

export const sitesApi = {
  list: () => api.get("/api/sites"),
  create: (payload) => api.post("/api/sites", payload),
};

export const stationsApi = {
  list: (params) => api.get("/api/stations", params),
  get: (id) => api.get(`/api/stations/${id}`),
  create: (payload) => api.post("/api/stations", payload),
  remove: (id) => api.delete(`/api/stations/${id}`),
  // porte seriali rilevate in questo momento dall'Edge Agent di quella
  // stazione (dal suo ultimo messaggio "hello") - vedi docs/api.md
  availablePorts: (id) => api.get(`/api/stations/${id}/available-ports`),
};
