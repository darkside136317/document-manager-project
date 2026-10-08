// Helpers of the XML exchange screen: which fields are chosen, how a job is shown, and following a running job.
import { cleanFilters } from "./reports.js";

const BASE = "/api/method/document_manager.document_manager.api.exchange";

/** The levels from the fonds down, with the DocType names the server uses. */
export const LEVEL_ORDER = ["Fonds", "Record Group", "Catalog", "Archival File", "Archive Document"];

export const levelIndex = (doctype) => LEVEL_ORDER.indexOf(doctype);

/** The levels an export of `doctype` writes in full: itself and, when asked, everything below it. */
export function exportedLevels(doctype, withChildren) {
  const from = levelIndex(doctype);
  if (from < 0) return [];
  return LEVEL_ORDER.slice(from, withChildren ? undefined : from + 1);
}

/** {doctype: Set(fieldnames)} with every field chosen, or only the given ones (what a file contains). */
export function allFields(levels, only = null) {
  const choice = {};
  for (const level of levels) {
    const names = level.fields.map((f) => f.fieldname).filter((name) => !only || name in (only[level.doctype] || {}));
    choice[level.doctype] = new Set(names);
  }
  return choice;
}

/** A chosen set after one field is switched; the key fields cannot be switched off. */
export function toggled(choice, level, fieldname) {
  if (level.fields.find((f) => f.fieldname === fieldname)?.key) return choice;
  const next = new Set(choice[level.doctype]);
  if (next.has(fieldname)) next.delete(fieldname);
  else next.add(fieldname);
  return { ...choice, [level.doctype]: next };
}

/** What the API takes: {doctype: [fieldnames]} for the given levels only. */
export function fieldsPayload(choice, doctypes) {
  const out = {};
  for (const doctype of doctypes) out[doctype] = [...(choice[doctype] || [])];
  return out;
}

export function countsRows(levels, counts, ancestors = {}) {
  return levels.map((level) => ({
    doctype: level.doctype, label: level.label, count: counts?.[level.doctype] ?? 0, ancestors: ancestors?.[level.doctype] ?? 0,
  }));
}

const TONES = { "Hoàn thành": "success", "Hoàn thành có lỗi": "warning", "Thất bại": "danger", "Đang xử lý": "info", "Chờ xử lý": "info", "Đã hủy": "muted", "Đã tải lên": "muted" };
export const jobTone = (status) => TONES[status] || "muted";

export const isBusy = (job) => Boolean(job && job.busy);

/** The state of a finished or running job in a few words, for the header of its card. */
export function jobHeadline(job) {
  if (!job) return "";
  if (job.busy) return job.phase ? `${job.status} — ${job.phase}` : job.status;
  return job.summary || job.status;
}

/** The levels a result has anything to say about, with their counters. */
export function resultRows(job, levels) {
  const per = job?.result?.levels;
  if (!per) return [];
  return levels
    .filter((level) => per[level.doctype] && Object.values(per[level.doctype]).some(Boolean))
    .map((level) => ({ doctype: level.doctype, label: level.label, ...per[level.doctype] }));
}

/**
 * Follow a job until it stops being busy. `fetch(name)` returns the job; `onUpdate(job)` hears every answer.
 * Resolves with the last job; `stop()` ends it early. The timer functions are parameters so tests need no clock.
 */
export function watchJob(name, { fetch, onUpdate = () => {}, interval = 1500, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let timer = null;
  let stopped = false;
  const done = new Promise((resolve, reject) => {
    const tick = async () => {
      if (stopped) return resolve(null);
      try {
        const job = await fetch(name);
        onUpdate(job);
        if (!isBusy(job)) return resolve(job);
      } catch (error) {
        return reject(error);
      }
      timer = setTimer(tick, interval);
    };
    tick();
  });
  return {
    done,
    stop() {
      stopped = true;
      clearTimer(timer);
    },
  };
}

export function downloadUrl(job) {
  return `${BASE}.download?job=${encodeURIComponent(job)}`;
}
export const schemaUrl = () => `${BASE}.download_schema`;

export { cleanFilters };
