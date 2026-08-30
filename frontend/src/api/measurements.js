import { api } from "./client";

export const measurementsApi = {
  list: (runId, params) => api.get(`/api/runs/${runId}/measurements`, params),
  create: (runId, payload) => api.post(`/api/runs/${runId}/measurements`, payload),
};
