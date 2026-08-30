import { api } from "./client";

export const calibrationsApi = {
  list: (params) => api.get("/api/calibrations", params),
  create: (payload) => api.post("/api/calibrations", payload),
  addResult: (id, payload) => api.post(`/api/calibrations/${id}/results`, payload),
  complete: (id, passed) => api.post(`/api/calibrations/${id}/complete`, undefined, { passed }),
  certificate: (id) => api.post(`/api/calibrations/${id}/certificate`),
};
