import { createRouter, createWebHistory } from "vue-router";
import { pageTitle } from "./lib/page.js";
import ArchiveBrowser from "./pages/ArchiveBrowser.vue";
import DashboardHome from "./pages/DashboardHome.vue";
import DocumentPage from "./pages/DocumentPage.vue";
import FilePage from "./pages/FilePage.vue";
import MasterPage from "./pages/MasterPage.vue";
import NotFound from "./pages/NotFound.vue";
import SearchPage from "./pages/SearchPage.vue";

// Frappe serves this app for /dashboard and every /dashboard/... path (hooks.website_route_rules).
export const routes = [
  { path: "/", name: "home", component: DashboardHome, meta: { title: "Tổng quan" } },
  { path: "/bien-muc", name: "archive", component: ArchiveBrowser, meta: { title: "Biên mục hồ sơ, văn bản" } },
  { path: "/ho-so/:name", name: "file", component: FilePage, meta: { title: "Hồ sơ" } },
  { path: "/van-ban/:name", name: "document", component: DocumentPage, meta: { title: "Văn bản" } },
  { path: "/tim-kiem", name: "search", component: SearchPage, meta: { title: "Tìm kiếm" } },
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
