// Data the Frappe host page (www/dashboard.py) embeds at start-up.
const empty = {
  csrf_token: "",
  user: { name: "", full_name: "", roles: [] },
  org: "Document Manager",
  nav: [],
  legacy: [],
  masters: [],
};

export const boot = { ...empty, ...(typeof window !== "undefined" ? window.__DM_BOOT__ : {}) };

export const csrfToken = () => boot.csrf_token;

export function masterBySlug(slug) {
  return boot.masters.find((m) => m.slug === slug) || null;
}

export function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}
