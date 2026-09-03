import { api } from "./client";

export const sitesApi = {
  list: () => api.get("/api/sites"),
  create: (payload) => api.post("/api/sites", payload),
  update: (id, payload) => api.put(`/api/sites/${id}`, payload),
  remove: (id) => api.delete(`/api/sites/${id}`),
};

export const stationsApi = {
  list: (params) => api.get("/api/stations", params),
  get: (id) => api.get(`/api/stations/${id}`),
  create: (payload) => api.post("/api/stations", payload),
  update: (id, payload) => api.put(`/api/stations/${id}`, payload),
  remove: (id) => api.delete(`/api/stations/${id}`),
  // porte seriali rilevate in questo momento dall'Edge Agent di quella
  // stazione (dal suo ultimo messaggio "hello") - vedi docs/api.md
  availablePorts: (id) => api.get(`/api/stations/${id}/available-ports`),
};
