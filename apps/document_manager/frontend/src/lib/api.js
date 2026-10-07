// Thin client for Frappe's /api/method/... : CSRF header, JSON, readable errors.
import { csrfToken } from "./boot.js";

export class ApiError extends Error {
  constructor(message, { status = 0, excType = "", messages = [] } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.excType = excType;
    this.messages = messages;
  }
}

/** Server messages are HTML snippets (links to the blocking records, <br>): reduce them to plain text. */
export function stripHtml(html) {
  return String(html ?? "")
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\/(p|li|div)>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** `_server_messages` is a JSON list of JSON strings: [{"message": "...", "indicator": "red"}, ...]. */
export function serverMessages(payload) {
  const raw = payload && payload._server_messages;
  if (!raw) return [];
  try {
    return JSON.parse(raw)
      .map((entry) => {
        try {
          return stripHtml(JSON.parse(entry).message);
        } catch {
          return stripHtml(entry);
        }
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

export function errorMessage(payload, status) {
  const messages = serverMessages(payload);
  if (messages.length) return messages.join("\n");
  if (status === 403) return "Bạn không có quyền thực hiện thao tác này.";
  if (status === 404) return "Không tìm thấy dữ liệu yêu cầu.";
  if (status === 409 || payload?.exc_type === "TimestampMismatchError") {
    return "Bản ghi vừa được người khác thay đổi. Hãy tải lại rồi sửa tiếp.";
  }
  if (status >= 500) return "Máy chủ gặp lỗi. Vui lòng thử lại sau.";
  return "Không thực hiện được yêu cầu.";
}

function toQuery(args) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(args)) {
    if (value === undefined || value === null || value === "") continue;
    params.append(key, typeof value === "object" ? JSON.stringify(value) : String(value));
  }
  return params.toString();
}

export function redirectToLogin() {
  const here = window.location.pathname + window.location.search;
  window.location.assign(`/login?redirect-to=${encodeURIComponent(here)}`);
}

/**
 * Call a whitelisted method. Reads use GET with the arguments in the query string; pass
 * `{ post: true }` for anything that changes data (Frappe requires POST + CSRF for those).
 */
export async function call(method, args = {}, { post = false, fetcher = fetch, loginOn401 = true } = {}) {
  const headers = { Accept: "application/json", "X-Frappe-CSRF-Token": csrfToken() };
  let url = `/api/method/${method}`;
  const init = { method: post ? "POST" : "GET", headers, credentials: "same-origin" };
  if (post) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(args);
  } else {
    const query = toQuery(args);
    if (query) url += `?${query}`;
  }

  let response;
  try {
    response = await fetcher(url, init);
  } catch {
    throw new ApiError("Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.");
  }
  const payload = await response.json().catch(() => ({}));
  // An expired session sends the user to the login page; a call that legitimately answers 401
  // (a wrong current password) opts out and shows its message instead.
  if (loginOn401 && (response.status === 401 || (response.status === 403 && payload?.exc_type === "AuthenticationError"))) {
    redirectToLogin();
  }
  if (!response.ok) {
    throw new ApiError(errorMessage(payload, response.status), {
      status: response.status,
      excType: payload?.exc_type || "",
      messages: serverMessages(payload),
    });
  }
  return payload.message;
}

const BASE = "document_manager.document_manager.api";
export const api = {
  boot: () => call(`${BASE}.boot.get_staff_boot`),
  summary: () => call(`${BASE}.dashboard.get_workspace_summary`),
  describe: (doctype) => call(`${BASE}.meta.get_doctype_ui`, { doctype }),
  list: (doctype, params = {}) => call(`${BASE}.crud.get_list`, { doctype, ...params }),
  get: (doctype, name) => call(`${BASE}.crud.get`, { doctype, name }),
  save: (doctype, values, name = null) => call(`${BASE}.crud.save`, { doctype, values, name }, { post: true }),
  remove: (doctype, name) => call(`${BASE}.crud.delete`, { doctype, name }, { post: true }),
  linkSearch: (doctype, txt = "", filters = null) => call(`${BASE}.crud.link_search`, { doctype, txt, filters }),
  treeChildren: (doctype, parent = null, filters = null) =>
    call(`${BASE}.crud.tree_children`, { doctype, parent, filters }),
  changePassword: (oldPassword, newPassword) =>
    call(
      "frappe.core.doctype.user.user.update_password",
      { old_password: oldPassword, new_password: newPassword, logout_all_sessions: 0 },
      { post: true, loginOn401: false }, // "Incorrect password" is a 401 too: do not log the user out
    ),
};
