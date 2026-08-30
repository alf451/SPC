import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/login", name: "login", component: () => import("../views/LoginView.vue"), meta: { public: true } },
  { path: "/", name: "dashboard", component: () => import("../views/DashboardView.vue") },
  { path: "/raccolta-dati", name: "data-collection", component: () => import("../views/DataCollectionView.vue") },
  { path: "/routine-quote", name: "config", component: () => import("../views/ConfigView.vue") },
  { path: "/strumenti", name: "gages", component: () => import("../views/GagesView.vue") },
  { path: "/amministrazione", name: "admin", component: () => import("../views/AdminView.vue") },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && auth.isAuthenticated) {
    return { name: "dashboard" };
  }
  return true;
});
