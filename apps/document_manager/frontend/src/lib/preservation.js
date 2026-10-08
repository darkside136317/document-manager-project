// Helpers of the preservation screens (module 7): the three kinds of job, how they are told, findings and sizes.

export const KINDS = {
  backup: { title: "Sao lưu", create: "Sao lưu mới", route: "/bao-quan/sao-luu", icon: "hard-drive",
    subtitle: "Sao lưu cơ sở dữ liệu và tệp tài liệu thành từng đợt; theo dõi, tải về, dọn các bản cũ." },
  integrity: { title: "Kiểm tra toàn vẹn", create: "Kiểm tra mới", route: "/bao-quan/kiem-tra", icon: "shield-check",
    subtitle: "Kiểm tra cơ sở dữ liệu, siêu dữ liệu và từng tệp tài liệu để phát hiện lỗi hoặc dữ liệu chưa đạt yêu cầu lưu trữ điện tử." },
  restore: { title: "Khôi phục", create: "Khôi phục tài liệu", route: "/bao-quan/khoi-phuc", icon: "undo",
    subtitle: "Khôi phục tệp của các tài liệu bị lỗi từ bản sao lưu, và chuẩn bị khôi phục cơ sở dữ liệu có kiểm soát." },
};

export const BACKUP_TYPES = [
  ["Cả hai", "Cơ sở dữ liệu và tệp tài liệu"], ["Cơ sở dữ liệu", "Chỉ cơ sở dữ liệu"], ["Tệp tài liệu", "Chỉ tệp tài liệu"],
];
export const CHECK_TYPES = [
  ["Toàn bộ", "Toàn bộ: cơ sở dữ liệu, siêu dữ liệu và từng tệp"], ["Cơ sở dữ liệu", "Cấu trúc cơ sở dữ liệu (liên kết, bộ đếm, ngày tháng, trùng lặp)"],
  ["Tệp tài liệu", "Từng tệp tài liệu (còn không, đúng mã kiểm, đúng loại, bản GridFS)"], ["Siêu dữ liệu", "Mô tả tài liệu (số, ngày, tác giả, vị trí lưu trữ)"],
];
export const STATUS_FILTERS = ["", "Chưa chạy", "Đang chờ", "Đang chạy", "Thành công", "Hoàn thành", "Phát hiện lỗi", "Một phần", "Cần thao tác thủ công", "Lỗi", "Đã hủy"];

const CODES = {
  FILE_MISSING: "Mất tệp", CHECKSUM: "Tệp đã thay đổi", FILE_EMPTY: "Tệp rỗng", TYPE_MISMATCH: "Sai loại tệp", GRIDFS_MISSING: "Mất bản GridFS",
  GRIDFS_NOT_STORED: "Chưa có bản GridFS", NO_ATTACHMENT: "Không còn tệp đính kèm", MONGO_DOWN: "Không kết nối MongoDB",
  ORPHAN_GROUP: "Khối mồ côi", ORPHAN_CATALOG: "Mục lục mồ côi", ORPHAN_FILE: "Hồ sơ mồ côi", ORPHAN_DOCUMENT: "Văn bản mồ côi",
  HIERARCHY_FILE: "Sai cấp bậc (hồ sơ)", HIERARCHY_DOCUMENT: "Sai cấp bậc (văn bản)", BROKEN_LEVEL_FILE: "Mức mật hỏng (hồ sơ)",
  BROKEN_LEVEL_DOCUMENT: "Mức mật hỏng (văn bản)", COUNTER_FONDS: "Sai bộ đếm phông", COUNTER_FILE: "Sai bộ đếm hồ sơ", DATE_FILE: "Ngày hồ sơ sai",
  DATE_FONDS: "Năm phông sai", DATE_FUTURE: "Ngày ở tương lai", DUPLICATE_FILE_NUMBER: "Trùng số hồ sơ", DUPLICATE_DOCUMENT_NUMBER: "Trùng số văn bản",
  NO_CHECKSUM: "Chưa có mã kiểm", INDEX_ERROR: "Lỗi chỉ mục",
};
export function codeLabel(code) {
  if (!code) return "";
  if (CODES[code]) return CODES[code];
  return code.startsWith("META_") ? "Thiếu siêu dữ liệu" : code;
}

/** The counters findings of this kind can be mended by recomputing them. */
export const isCounterCode = (code) => code === "COUNTER_FONDS" || code === "COUNTER_FILE";

export function jobType(kind, job) {
  return kind === "backup" ? job.backup_type : kind === "integrity" ? job.check_type : job.restore_type;
}

/** What a job did, in a few words, for the list. */
export function jobResult(kind, job) {
  if (kind === "backup") {
    const parts = [];
    if (job.database?.file) parts.push(`CSDL ${formatMb(job.database.size_mb)}`);
    if (job.files?.total || job.files?.done) parts.push(`${job.files.done}/${job.files.total} tệp${job.files.failed ? `, ${job.files.failed} lỗi` : ""}`);
    return parts.join(" · ") || "—";
  }
  if (kind === "integrity") return job.total_checked || job.errors || job.warnings ? `${job.total_checked} tài liệu · ${job.errors} lỗi · ${job.warnings} cảnh báo` : "—";
  return job.restore_type === "Cơ sở dữ liệu" ? "Cơ sở dữ liệu" : `${job.restored}/${job.total} tài liệu${job.failed ? `, ${job.failed} lỗi` : ""}`;
}

export function formatMb(value) {
  const n = Number(value) || 0;
  return n >= 1024 ? `${(n / 1024).toFixed(1)} GB` : `${n.toFixed(n < 10 && n % 1 ? 1 : 0)} MB`;
}

export function formatBytes(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

/** "3 ngày trước" for the age of the last backup; null/undefined: never. */
export function ageText(days) {
  if (days === null || days === undefined) return "chưa có";
  if (days === 0) return "hôm nay";
  return `${days} ngày trước`;
}

/** Tone of a backup's age against the schedule: red when a scheduled backup is overdue. */
export function ageTone(days, frequency) {
  if (days === null || days === undefined) return "danger";
  const limit = { "Hàng ngày": 2, "Hàng tuần": 9, "Hàng tháng": 35 }[frequency] ?? 9;
  return days > limit ? "danger" : days > limit / 2 ? "warning" : "success";
}

/** Names of documents typed or pasted (one per line, commas or spaces): trimmed, unique, in order. */
export function parseNames(text) {
  return [...new Set(String(text || "").split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
}

/** Can the user type the site name to run a database restore? */
export const confirmMatches = (typed, site) => Boolean(site) && String(typed || "").trim() === site;

export const downloadBackupUrl = (name, which = "database") =>
  `/api/method/document_manager.document_manager.api.preservation.download_backup?name=${encodeURIComponent(name)}&which=${which}`;
