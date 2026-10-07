// Helpers of the reader-registration queue (/dashboard/doc-gia/dang-ky).
import { reactive } from "vue";
import { boot } from "./boot.js";

export const REGISTRATIONS_ROUTE = "/dashboard/doc-gia/dang-ky";

/** Counters shown next to sidebar entries; they start from the boot data and pages keep them current. */
export const badges = reactive(
  Object.fromEntries(boot.nav.flatMap((group) => group.items).filter((item) => item.badge).map((item) => [item.route, item.badge])),
);

export const STATUS_FILTERS = [
  { value: "Mới", label: "Chờ xử lý" },
  { value: "Đã duyệt", label: "Đã duyệt" },
  { value: "Từ chối", label: "Đã từ chối" },
  { value: "", label: "Tất cả" },
];

export const TYPE_FILTERS = [
  { value: "", label: "Mọi loại yêu cầu" },
  { value: "Đăng ký tài khoản", label: "Đăng ký tài khoản" },
  { value: "Quên mật khẩu", label: "Quên mật khẩu" },
];

export const isResetRequest = (row) => row?.request_type === "Quên mật khẩu";

/** The status-badge tone of a registration. */
export const registrationTone = (status) => ({ Mới: "warning", "Đã duyệt": "success", "Từ chối": "danger" })[status] || "muted";

/** Absolute URL of a one-time link returned as a site-relative path (what the officer passes on). */
export function absoluteLink(path, origin = typeof window !== "undefined" ? window.location.origin : "") {
  return /^https?:\/\//i.test(path) ? path : `${origin}${path}`;
}

/** What a request asks for, in one line, for the confirmation texts. */
export function describeRequest(row) {
  const who = `${row.full_name} <${row.email}>`;
  return isResetRequest(row) ? `Cấp lại mật khẩu cho ${who}` : `Tạo tài khoản độc giả cho ${who}`;
}

export function setPendingBadge(count) {
  if (count > 0) badges[REGISTRATIONS_ROUTE] = count;
  else delete badges[REGISTRATIONS_ROUTE];
}
