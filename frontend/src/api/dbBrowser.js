import { api } from "./client";

export const dbBrowserApi = {
  tables: () => api.get("/api/admin/db/tables"),
  rows: (table, params) => api.get(`/api/admin/db/tables/${encodeURIComponent(table)}/rows`, params),
};
