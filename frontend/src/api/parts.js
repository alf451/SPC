import { api } from "./client";

export const partsApi = {
  listFolders: () => api.get("/api/part-folders"),
  list: (params) => api.get("/api/parts", params),
  get: (id) => api.get(`/api/parts/${id}`),
  create: (payload) => api.post("/api/parts", payload),
};
