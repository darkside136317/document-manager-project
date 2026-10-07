// Description of a DocType (fields, layout, permissions) from the server, cached per page load.
import { api } from "./api.js";

const cache = new Map();

export function describe(doctype) {
  if (!cache.has(doctype)) {
    const request = api.describe(doctype).catch((error) => {
      cache.delete(doctype); // do not cache failures
      throw error;
    });
    cache.set(doctype, request);
  }
  return cache.get(doctype);
}

export function clearDescriptions() {
  cache.clear();
}

export const fieldByName = (meta, fieldname) => meta.fields.find((f) => f.fieldname === fieldname);

/** Today as YYYY-MM-DD in the browser's time zone (Frappe's "Today" default means the user's today). */
export const isoDate = (date = new Date()) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

/** Value a new record starts with: the DocType defaults, checkboxes as 0/1, the rest empty. */
export function blankRecord(meta, overrides = {}) {
  const record = {};
  for (const field of meta.fields) {
    let value = field.default;
    if (field.fieldtype === "Table") {
      record[field.fieldname] = [];
      continue;
    }
    if (field.fieldtype === "Date" && value === "Today") value = isoDate();
    else if (field.fieldtype === "Datetime" && (value === "Now" || value === "Today")) value = `${isoDate()} ${new Date().toTimeString().slice(0, 8)}`;
    else if (field.fieldtype === "Check") value = value === "1" || value === 1 ? 1 : 0;
    else if (field.fieldtype === "Int") value = value === undefined || value === "" || value === null ? null : Number(value);
    else if (field.fieldtype === "Float") value = value === undefined || value === "" || value === null ? null : Number(value);
    else if (value === undefined || value === null) value = "";
    record[field.fieldname] = value;
  }
  return { ...record, ...overrides };
}

/** A new row of a child table: each column's default, checkboxes as 0/1, numbers as numbers. */
export function blankRow(columns) {
  const row = {};
  for (const column of columns) {
    let value = column.default;
    if (column.fieldtype === "Check") value = value === "1" || value === 1 ? 1 : 0;
    else if (column.fieldtype === "Int" || column.fieldtype === "Float") value = value === undefined || value === "" || value === null ? null : Number(value);
    else if (value === undefined || value === null) value = "";
    row[column.fieldname] = value;
  }
  return row;
}

/** The options of a Select field, as the DocType stores them (one per line, first may be blank). */
export function selectOptions(field) {
  return String(field.options || "").split("\n");
}

/** Fields the user fills in (in layout order); the server already removed what they cannot see. */
export function formFieldNames(meta) {
  return meta.layout.flatMap((section) => section.columns.flat());
}

/** Required fields that are still empty: [{fieldname, label}]. */
export function missingRequired(meta, record) {
  return meta.fields
    .filter((f) => f.reqd && !f.read_only && f.fieldtype !== "Check" && isVisible(f.depends_on, record))
    .filter((f) => {
      const value = record[f.fieldname];
      if (f.fieldtype === "Table") return !value || !value.length;
      return value === "" || value === null || value === undefined;
    })
    .map((f) => ({ fieldname: f.fieldname, label: f.label }));
}

const OPERAND = String.raw`(?:'([^']*)'|"([^"]*)"|(-?\d+(?:\.\d+)?)|(true|false))`;
const COMPARE = new RegExp(String.raw`^doc\.(\w+)\s*(==|===|!=|!==)\s*${OPERAND}$`);

/**
 * Is a field (or section) shown? Frappe's `depends_on` is either a field name or `eval:doc.field == 'x'`
 * (also `!=`, a bare `doc.field` for "has a value"). Anything else is treated as shown: the server still
 * validates, this only keeps the form from asking for what does not apply.
 */
export function isVisible(expression, record) {
  const text = String(expression || "").trim();
  if (!text) return true;
  const code = text.startsWith("eval:") ? text.slice(5).trim() : `doc.${text}`;
  const truthy = (value) => Boolean(value) && value !== "0";
  const bare = /^doc\.(\w+)$/.exec(code);
  if (bare) return truthy(record[bare[1]]);
  const negated = /^!\s*doc\.(\w+)$/.exec(code);
  if (negated) return !truthy(record[negated[1]]);
  const m = COMPARE.exec(code);
  if (!m) return true;
  const [, field, op] = m;
  const wanted = [m[3], m[4], m[5], m[6]].find((v) => v !== undefined);
  const actual = record[field];
  const equal = String(actual ?? "") === String(wanted) || (wanted === "true" && truthy(actual)) || (wanted === "false" && !truthy(actual));
  return op.startsWith("==") ? equal : !equal;
}
