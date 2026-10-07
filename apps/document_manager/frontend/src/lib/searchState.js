// Search state <-> URL query <-> API parameters, and the user's saved filters.

export const TABS = {
  "ho-so": { label: "Hồ sơ", fields: ["fonds", "record_group", "catalog", "file_title", "file_number", "confidentiality_level", "status", "storage_warehouse", "start_date_from", "start_date_to"] },
  "van-ban": { label: "Văn bản", fields: ["fonds", "archival_file", "file_type", "confidentiality_level", "document_title", "document_number", "author", "date_from", "date_to"] },
};
export const SORTS = [
  { value: "", label: "Mới cập nhật" },
  { value: "newest", label: "Mới nhất" },
  { value: "oldest", label: "Cũ nhất" },
  { value: "title", label: "Theo tiêu đề" },
];

const clean = (obj) => Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== "" && v !== null && v !== undefined));

export function emptyState(tab = "van-ban") {
  return { tab, q: "", sort: "", page: 1, filters: {}, advanced: false };
}

/** Parse a vue-router `query` object. Unknown tab/filter names are dropped. */
export function fromQuery(query = {}) {
  const tab = TABS[query.tab] ? query.tab : "van-ban";
  const filters = {};
  for (const name of TABS[tab].fields) if (query[name]) filters[name] = String(query[name]);
  return {
    tab,
    q: String(query.q || ""),
    sort: SORTS.some((s) => s.value === query.sort) ? String(query.sort) : "",
    page: Math.max(1, Number(query.page) || 1),
    filters,
    advanced: Object.keys(filters).length > 0 || query.advanced === "1",
  };
}

export function toQuery(state) {
  return clean({
    tab: state.tab,
    q: state.q.trim(),
    sort: state.sort,
    page: state.page > 1 ? String(state.page) : "",
    ...state.filters,
  });
}

/** Parameters of search_archival_files / search_documents. */
export function toApiParams(state, pageSize = 20) {
  const allowed = new Set(TABS[state.tab].fields);
  const filters = Object.fromEntries(Object.entries(clean(state.filters)).filter(([k]) => allowed.has(k)));
  return clean({ query: state.q.trim(), ...filters, sort_by: state.sort, page: state.page, page_size: pageSize });
}

export const hasCriteria = (state) => Boolean(state.q.trim()) || Object.keys(clean(state.filters)).length > 0;

/** Keep only `<mark>` of an engine highlight; everything else is shown as text. */
export function safeHighlight(html) {
  const text = String(html ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return text.replace(/&lt;mark&gt;/g, "<mark>").replace(/&lt;\/mark&gt;/g, "</mark>");
}

// ---- saved filters (a convenience of this browser: failures to read/write are ignored) --------------
const KEY = "dm-saved-filters";

export function loadSaved() {
  try {
    const list = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(list) ? list.filter((s) => s && s.name && s.query) : [];
  } catch {
    return [];
  }
}

function persist(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* private window or blocked storage */
  }
  return list;
}

export function saveFilter(name, state) {
  const entry = { name: name.trim(), query: toQuery({ ...state, page: 1 }) };
  if (!entry.name) return loadSaved();
  return persist([...loadSaved().filter((s) => s.name !== entry.name), entry].sort((a, b) => a.name.localeCompare(b.name, "vi")));
}

export function deleteSaved(name) {
  return persist(loadSaved().filter((s) => s.name !== name));
}
