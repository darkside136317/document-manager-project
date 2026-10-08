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
  window.location.assign(`/dang-nhap?redirect-to=${encodeURIComponent(here)}`);
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
  archive: {
    tree: (parentDoctype = null, parentName = null) =>
      call(`${BASE}.archive.get_tree`, { parent_doctype: parentDoctype, parent_name: parentName }),
    fileOverview: (name) => call(`${BASE}.archive.get_file_overview`, { name }),
    documentOverview: (name) => call(`${BASE}.archive.get_document_overview`, { name }),
    addDocument: (archivalFile, fileUrl, title = null) =>
      call(`${BASE}.archive.add_document_from_file`, { archival_file: archivalFile, file_url: fileUrl, title }, { post: true }),
    attachFile: (document, fileUrl) =>
      call(`${BASE}.archive.attach_file`, { document, file_url: fileUrl }, { post: true }),
    reindex: (document) => call(`${BASE}.archive.reindex_document`, { document }, { post: true }),
  },
  search: {
    files: (params) => call(`${BASE}.search.search_archival_files`, params),
    documents: (params) => call(`${BASE}.search.search_documents`, params),
  },
  registrations: {
    list: (params) => call(`${BASE}.registration.list_registrations`, params),
    pending: () => call(`${BASE}.registration.pending_registrations`),
    groups: () => call(`${BASE}.registration.reader_groups`),
    approve: (name, readerGroup) =>
      call(`${BASE}.registration.approve_registration`, { name, reader_group: readerGroup || null }, { post: true }),
    reject: (name, reason) => call(`${BASE}.registration.reject_registration`, { name, reason }, { post: true }),
    reissue: (name) => call(`${BASE}.registration.reissue_link`, { name }, { post: true }),
  },
  slips: {
    summary: () => call(`${BASE}.slips.queue_summary`),
    badges: () => call(`${BASE}.slips.queue_badges`),
    list: (kind, params = {}) => call(`${BASE}.slips.list_slips`, { kind, ...params }),
    get: (kind, name) => call(`${BASE}.slips.get_slip`, { kind, name }),
    decideItems: (kind, name, decisions) => call(`${BASE}.slips.decide_items`, { kind, name, decisions }, { post: true }),
    receiveReturn: (name, conditions) => call(`${BASE}.slips.receive_return`, { name, conditions }, { post: true }),
    renew: (name) => call(`${BASE}.slips.renew`, { name }, { post: true }),
    deleteDraft: (kind, name) => call(`${BASE}.slips.delete_draft`, { kind, name }, { post: true }),
    readerSlips: (reader) => call(`${BASE}.slips.reader_slips`, { reader }),
  },
  requests: {
    action: (doctype, name, action, text) => call(`${BASE}.requests.apply_action`, { doctype, name, action, text }, { post: true }),
    save: (doctype, payload, name = null, submit = false) =>
      call(`${BASE}.requests.save_request`, { doctype, payload, name, submit: submit ? 1 : 0 }, { post: true }),
  },
  feedback: {
    list: (params = {}) => call(`${BASE}.feedback.list_feedback`, params),
    get: (name) => call(`${BASE}.feedback.get_feedback`, { name }),
  },
  reports: {
    list: () => call(`${BASE}.reports.list_reports`),
    get: (slug) => call(`${BASE}.reports.get_report`, { slug }),
    run: (slug, filters = {}, page = 1, pageSize = 50) =>
      call(`${BASE}.reports.run_report`, { slug, filters, page, page_size: pageSize }),
  },
  inventory: {
    populate: (name) => call(`${BASE}.inventory.populate`, { name }, { post: true }),
    complete: (name) => call(`${BASE}.inventory.complete`, { name }, { post: true }),
    reopen: (name) => call(`${BASE}.inventory.reopen`, { name }, { post: true }),
  },
  exchange: {
    capabilities: () => call(`${BASE}.exchange.capabilities`),
    previewExport: (level, filters, includeChildren) =>
      call(`${BASE}.exchange.preview_export`, { level, filters, include_children: includeChildren ? 1 : 0 }),
    startExport: (level, filters, fields, includeChildren) =>
      call(`${BASE}.exchange.start_export`, { level, filters, fields, include_children: includeChildren ? 1 : 0 }, { post: true }),
    analyze: (fileUrl) => call(`${BASE}.exchange.analyze_import`, { file_url: fileUrl }, { post: true }),
    startImport: (job, options) => call(`${BASE}.exchange.start_import`, { job, ...options }, { post: true }),
    job: (job) => call(`${BASE}.exchange.get_job`, { job }),
    jobs: (params = {}) => call(`${BASE}.exchange.list_jobs`, params),
    cancel: (job) => call(`${BASE}.exchange.cancel_job`, { job }, { post: true }),
    remove: (job) => call(`${BASE}.exchange.delete_job`, { job }, { post: true }),
  },
  readerAccess: (reader) => call(`${BASE}.registration.issue_reader_access`, { reader }, { post: true }),
  preview: (docName) => call(`${BASE}.file_access.get_preview`, { doc_name: docName }),
  // Own endpoint: a wrong current password must not end the session (Frappe's update_password would).
  changePassword: (oldPassword, newPassword) =>
    call(`${BASE}.account.change_password`, { old_password: oldPassword, new_password: newPassword }, { post: true, loginOn401: false }),
};
