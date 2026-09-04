import { api } from "./client";

export const notificationSettingsApi = {
  get: () => api.get("/api/notification-settings"),
  update: (payload) => api.put("/api/notification-settings", payload),
  test: () => api.post("/api/notification-settings/test"),
};

export const supportApi = {
  send: (payload) => api.post("/api/support/request", payload),
};
