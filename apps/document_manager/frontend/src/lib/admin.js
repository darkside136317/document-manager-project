// Helpers of the administration screens (module 8): users, the permission matrix, the system log and the monitor.
import { formatNumber } from "./format.js";

export const ROLE_ORDER = ["Document Admin", "Archive Leader", "Cataloger", "Reading Room Officer", "Preservation Officer"];

/** Initial values of the user form; the staff roles it may give come from the server. */
export function blankUser() {
  return { email: "", first_name: "", last_name: "", phone: "", enabled: 1, roles: [], groups: [] };
}

export function userToForm(user) {
  return { email: user.name, first_name: user.first_name, last_name: user.last_name, phone: user.phone, enabled: user.enabled, roles: [...user.roles], groups: [...user.groups] };
}

/** Roles in the order the screen shows them, whatever order the user holds them in. */
export const sortRoles = (roles) => [...roles].sort((a, b) => ROLE_ORDER.indexOf(a) - ROLE_ORDER.indexOf(b));

export function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Only what changed, so an edit never resends (and never overwrites) what the form did not touch. */
export function changedValues(original, form) {
  const out = {};
  for (const key of ["first_name", "last_name", "phone", "enabled"]) if (form[key] !== original[key]) out[key] = form[key];
  for (const key of ["roles", "groups"]) {
    if (JSON.stringify(sortRoles(form[key])) !== JSON.stringify(sortRoles(original[key]))) out[key] = form[key];
  }
  return out;
}

/** Why a user form cannot be sent yet ("" when it can). */
export function userProblem(form, creating) {
  if (creating && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(form.email).trim())) return "Nhập địa chỉ email hợp lệ";
  if (!String(form.first_name).trim()) return "Nhập tên";
  return "";
}

/** Can the current user change this account in the screen at all? (the server enforces the same rules) */
export function canEditUser(user, me) {
  if (!user) return false;
  if (user.protected) return me.roles.includes("System Manager") || me.name === "Administrator";
  return true;
}

export const permissionIcons = [["read", "Xem"], ["create", "Thêm"], ["write", "Sửa"], ["delete", "Xóa"]];

/** Compact text of what a role may do on a DocType: "Xem, Thêm, Sửa". */
export function permissionText(perms) {
  const given = permissionIcons.filter(([key]) => perms?.[key]).map(([, label]) => label);
  return given.length ? given.join(", ") : "Không";
}

// --- the system log -------------------------------------------------------------------------------------------------

export const LOG_FILTERS = ["activity_type", "user", "reference_doctype", "reference_name", "search", "date_from", "date_to"];

export function cleanLogFilters(values) {
  const out = {};
  for (const key of LOG_FILTERS) if (values[key]) out[key] = String(values[key]).trim();
  return out;
}

export function logDownloadUrl(filters) {
  const params = new URLSearchParams(cleanLogFilters(filters));
  return `/api/method/document_manager.document_manager.api.logs.download_logs?${params}`;
}

/** The newest date a clean-up may reach: the server never cleans the last `keepDays` days. */
export function latestPurgeDate(keepDays = 7, today = new Date()) {
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - keepDays);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** The count must be typed back exactly before a clean-up is offered. */
export const purgeConfirmed = (typed, total) => total > 0 && String(typed).replace(/\D/g, "") === String(total);

export function prettyJson(text) {
  if (!text) return "";
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return String(text);
  }
}

// --- the monitor ----------------------------------------------------------------------------------------------------

export function serviceTone(service) {
  return service?.ok ? "success" : "danger";
}

export function diskTone(disk) {
  if (!disk) return "muted";
  return disk.used_percent >= 90 ? "danger" : disk.used_percent >= 75 ? "warning" : "success";
}

export function indexTone(documents) {
  if (!documents?.total) return "success";
  return documents.errors ? "danger" : documents.percent >= 95 ? "success" : "warning";
}

export const queueText = (queues) => (queues || []).map((q) => `${q.name}: ${formatNumber(q.jobs)}`).join(" · ") || "—";
