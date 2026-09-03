import { api } from "./client";

export const usersApi = {
  list: () => api.get("/api/users"),
  create: (payload) => api.post("/api/users", payload),
  update: (id, payload) => api.put(`/api/users/${id}`, payload),
};
