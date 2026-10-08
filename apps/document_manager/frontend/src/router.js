import { createRouter, createWebHistory } from "vue-router";
import { pageTitle } from "./lib/page.js";
import ArchiveBrowser from "./pages/ArchiveBrowser.vue";
import DashboardHome from "./pages/DashboardHome.vue";
import DocumentPage from "./pages/DocumentPage.vue";
import ExchangePage from "./pages/ExchangePage.vue";
import FilePage from "./pages/FilePage.vue";
import MasterPage from "./pages/MasterPage.vue";
import NotFound from "./pages/NotFound.vue";
import FeedbackPage from "./pages/FeedbackPage.vue";
import RegistrationsPage from "./pages/RegistrationsPage.vue";
import ReportPage from "./pages/ReportPage.vue";
import ReportsHub from "./pages/ReportsHub.vue";
import SlipPage from "./pages/SlipPage.vue";
import SlipsPage from "./pages/SlipsPage.vue";
import SearchPage from "./pages/SearchPage.vue";

// Frappe serves this app for /dashboard and every /dashboard/... path (hooks.website_route_rules).
export const routes = [
  { path: "/", name: "home", component: DashboardHome, meta: { title: "Tổng quan" } },
  { path: "/bien-muc", name: "archive", component: ArchiveBrowser, meta: { title: "Biên mục hồ sơ, văn bản" } },
  { path: "/ho-so/:name", name: "file", component: FilePage, meta: { title: "Hồ sơ" } },
  { path: "/van-ban/:name", name: "document", component: DocumentPage, meta: { title: "Văn bản" } },
  { path: "/tim-kiem", name: "search", component: SearchPage, meta: { title: "Tìm kiếm" } },
  { path: "/doc-gia/dang-ky", name: "registrations", component: RegistrationsPage, meta: { title: "Đăng ký độc giả" } },
  { path: "/doc-gia/phieu-su-dung", name: "slips-usage", component: SlipsPage, props: { kind: "usage" }, meta: { title: "Phiếu yêu cầu sử dụng" } },
  { path: "/doc-gia/phieu-su-dung/:name", name: "slip-usage", component: SlipPage, props: (route) => ({ kind: "usage", name: route.params.name }), meta: { title: "Phiếu yêu cầu sử dụng" } },
  { path: "/doc-gia/phieu-sao-chup", name: "slips-copy", component: SlipsPage, props: { kind: "copy" }, meta: { title: "Phiếu sao chụp" } },
  { path: "/doc-gia/phieu-sao-chup/:name", name: "slip-copy", component: SlipPage, props: (route) => ({ kind: "copy", name: route.params.name }), meta: { title: "Phiếu sao chụp" } },
  { path: "/doc-gia/gop-y", name: "feedback", component: FeedbackPage, meta: { title: "Góp ý của độc giả" } },
  { path: "/doc-gia/:slug", name: "reader-screen", component: MasterPage, meta: { title: "Độc giả", sources: ["readers", "settings"] } },
  { path: "/bao-cao", name: "reports", component: ReportsHub, meta: { title: "Thống kê, báo cáo" } },
  { path: "/bao-cao/:slug", name: "report", component: ReportPage, props: true, meta: { title: "Báo cáo" } },
  { path: "/kiem-ke", name: "inventory", component: MasterPage, meta: { title: "Tổng kiểm kê phông", slug: "kiem-ke", sources: ["inventory"] } },
  { path: "/trao-doi-du-lieu", name: "exchange", component: ExchangePage, meta: { title: "Xuất, nhập dữ liệu XML" } },
  { path: "/danh-muc/:slug", name: "master", component: MasterPage, meta: { title: "Danh mục", sources: ["masters"] } },
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound, meta: { title: "Không tìm thấy" } },
];

export function createAppRouter(history = createWebHistory("/dashboard")) {
  const router = createRouter({ history, routes, scrollBehavior: () => ({ top: 0 }) });
  router.afterEach(() => {
    pageTitle.value = "";
  });
  return router;
}
