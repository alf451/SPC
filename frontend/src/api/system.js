import { api } from "./client";

export const systemApi = {
  version: () => api.get("/api/version"),
  changelog: () => api.get("/api/changelog"),
};
