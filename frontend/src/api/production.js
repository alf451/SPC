import { api } from "./client";

export const toolsApi = {
  list: () => api.get("/api/tools"),
  create: (payload) => api.post("/api/tools", payload),
  positions: (id) => api.get(`/api/tools/${id}/positions`),
  remove: (id) => api.delete(`/api/tools/${id}`),
};

export const workOrdersApi = {
  list: (params) => api.get("/api/work-orders", params),
  create: (payload) => api.post("/api/work-orders", payload),
};
