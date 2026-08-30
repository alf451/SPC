import { api } from "./client";

export const daqDevicesApi = {
  list: () => api.get("/api/daq-devices"),
  create: (payload) => api.post("/api/daq-devices", payload),
  remove: (id) => api.delete(`/api/daq-devices/${id}`),
};

export const daqSourcesApi = {
  list: (params) => api.get("/api/daq-sources", params),
  create: (payload) => api.post("/api/daq-sources", payload),
  remove: (id) => api.delete(`/api/daq-sources/${id}`),
  test: (id) => api.post(`/api/daq-sources/${id}/test`),
};

export const featureDaqBindingsApi = {
  set: (payload) => api.put("/api/feature-daq-bindings", payload),
  // il backend legge routine_id/feature_id come query param su DELETE, non body
  remove: (routineId, featureId) =>
    api.delete("/api/feature-daq-bindings", { routine_id: routineId, feature_id: featureId }),
};
