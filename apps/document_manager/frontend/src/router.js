import { createRouter, createWebHistory } from "vue-router";
import { pageTitle } from "./lib/page.js";
import DashboardHome from "./pages/DashboardHome.vue";
import MasterPage from "./pages/MasterPage.vue";
import NotFound from "./pages/NotFound.vue";

// Frappe serves this app for /dashboard and every /dashboard/... path (hooks.website_route_rules).
export const routes = [
  { path: "/", name: "home", component: DashboardHome, meta: { title: "Tổng quan" } },
  { path: "/danh-muc/:slug", name: "master", component: MasterPage, meta: { title: "Danh mục" } },
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound, meta: { title: "Không tìm thấy" } },
];

export function createAppRouter(history = createWebHistory("/dashboard")) {
  const router = createRouter({ history, routes, scrollBehavior: () => ({ top: 0 }) });
  router.afterEach(() => {
    pageTitle.value = "";
  });
  return router;
}
