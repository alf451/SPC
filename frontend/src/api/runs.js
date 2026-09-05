import { api } from "./client";

export const runsApi = {
  list: (params) => api.get("/api/runs", params),
  get: (id) => api.get(`/api/runs/${id}`),
  create: (payload) => api.post("/api/runs", payload),
  complete: (id) => api.post(`/api/runs/${id}/complete`),
  setCurrentPosition: (id, toolPositionId) => api.put(`/api/runs/${id}/current-position`, { tool_position_id: toolPositionId }),
  skipPosition: (id, toolPositionId) => api.post(`/api/runs/${id}/skip-position`, { tool_position_id: toolPositionId }),
  unskipPosition: (id, toolPositionId) => api.delete(`/api/runs/${id}/skip-position/${toolPositionId}`),
  positionProgress: (id) => api.get(`/api/runs/${id}/position-progress`),
  getTraceability: (id) => api.get(`/api/runs/${id}/traceability`),
  setTraceability: (id, fieldName, value) => api.put(`/api/runs/${id}/traceability/${encodeURIComponent(fieldName)}`, { value }),
};
