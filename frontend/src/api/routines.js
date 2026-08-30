import { api } from "./client";

export const routinesApi = {
  listFolders: () => api.get("/api/routine-folders"),
  list: (params) => api.get("/api/routines", params),
  get: (id) => api.get(`/api/routines/${id}`),
  create: (payload) => api.post("/api/routines", payload),
  features: (id) => api.get(`/api/routines/${id}/features`),
  setFeatureBinding: (id, featureId, payload) => api.put(`/api/routines/${id}/features/${featureId}`, payload),
};
