import { api } from "./client";

export const runsApi = {
  list: (params) => api.get("/api/runs", params),
  get: (id) => api.get(`/api/runs/${id}`),
  create: (payload) => api.post("/api/runs", payload),
  complete: (id) => api.post(`/api/runs/${id}/complete`),
};
