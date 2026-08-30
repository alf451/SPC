import { api } from "./client";

export const featuresApi = {
  listByPart: (partId) => api.get(`/api/parts/${partId}/features`),
  create: (payload) => api.post("/api/features", payload),
  propertyVersions: (id) => api.get(`/api/features/${id}/properties`),
  addPropertyVersion: (id, payload) => api.post(`/api/features/${id}/properties`, payload),
};
