import { api } from "./client";

export const gagesApi = {
  list: () => api.get("/api/gages"),
  get: (id) => api.get(`/api/gages/${id}`),
  create: (payload) => api.post("/api/gages", payload),
};
