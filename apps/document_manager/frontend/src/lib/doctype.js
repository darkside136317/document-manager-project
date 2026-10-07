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

/** Value a new record starts with: the DocType defaults, checkboxes as 0/1, the rest empty. */
export function blankRecord(meta, overrides = {}) {
  const record = {};
  for (const field of meta.fields) {
    let value = field.default;
    if (field.fieldtype === "Check") value = value === "1" || value === 1 ? 1 : 0;
    else if (field.fieldtype === "Int") value = value === undefined || value === "" || value === null ? null : Number(value);
    else if (field.fieldtype === "Float") value = value === undefined || value === "" || value === null ? null : Number(value);
    else if (value === undefined || value === null) value = "";
    record[field.fieldname] = value;
  }
  return { ...record, ...overrides };
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
    .filter((f) => f.reqd && !f.read_only && f.fieldtype !== "Check")
    .filter((f) => record[f.fieldname] === "" || record[f.fieldname] === null || record[f.fieldname] === undefined)
    .map((f) => ({ fieldname: f.fieldname, label: f.label }));
}
