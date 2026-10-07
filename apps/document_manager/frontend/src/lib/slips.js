// Helpers of the slip queues (phiếu yêu cầu sử dụng, phiếu sao chụp) of the staff app.

export const KINDS = {
  usage: {
    kind: "usage", doctype: "Usage Request", route: "/doc-gia/phieu-su-dung", label: "Phiếu yêu cầu sử dụng",
    short: "phiếu sử dụng", purposeLabel: "Mục đích sử dụng",
  },
  copy: {
    kind: "copy", doctype: "Copy Request", route: "/doc-gia/phieu-sao-chup", label: "Phiếu sao chụp",
    short: "phiếu sao chụp", purposeLabel: "Mục đích sao chụp",
  },
};

export const kindOf = (value) => KINDS[value] || KINDS.usage;

export const CONDITIONS = ["Tốt", "Hư hỏng nhẹ", "Thiếu trang", "Hư hỏng nặng"];

/** How a workflow action looks as a button: primary (moves the slip on), danger (turns it down), plain. */
export function actionStyle(action) {
  if (["Duyệt", "Giao tài liệu", "Nhận trả", "Hoàn thành", "Chuyển lãnh đạo", "Gửi duyệt"].includes(action)) return "btn-primary";
  if (["Từ chối", "Hủy phiếu"].includes(action)) return "btn-danger";
  return "";
}

/** Actions that need a written reason before they run. */
export const needsReason = (action) => action === "Từ chối";

/** Actions that ask for confirmation (they cannot be undone from the screen). */
export const needsConfirm = (action) => ["Hủy phiếu", "Giao tài liệu", "Hoàn thành"].includes(action);

export const confirmText = (action, slip) => {
  const what = `${slip.doctype === "Usage Request" ? "phiếu yêu cầu sử dụng" : "phiếu sao chụp"} ${slip.name}`;
  return {
    "Hủy phiếu": `Hủy ${what}? Phiếu sẽ không dùng được nữa.`,
    "Giao tài liệu": `Giao tài liệu của ${what} cho ${slip.reader?.full_name || "độc giả"}? Hạn trả được tính từ hôm nay.`,
    "Hoàn thành": `Xác nhận đã sao chụp xong và giao bản sao của ${what}?`,
  }[action];
};

/** Items the officer or leader may decide on, as the API expects them. */
export function decisionsFrom(items) {
  return items.map((item) => ({ row: item.row, status: item.item_status, note: item.decision_note || "" }));
}

/** An item turned down needs its reason; returns the rows that do not have one. */
export const rejectedWithoutReason = (items) => items.filter((i) => i.item_status === "Từ chối" && !String(i.decision_note || "").trim());

export const approvedCount = (items) => items.filter((i) => i.item_status !== "Từ chối").length;

export function daysLate(dueDate, today = new Date()) {
  if (!dueDate) return 0;
  const due = new Date(`${String(dueDate).slice(0, 10)}T00:00:00`);
  const now = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.max(0, Math.round((now - due) / 86400000));
}

/** The view a screen opens on, in the URL when given and valid, else the server's suggestion. */
export function pickView(requested, views, fallback) {
  return views.some((v) => v.view === requested) ? requested : fallback;
}

/** Tab counter text: 0 is shown as nothing, big numbers stay readable. */
export const counter = (n) => (n > 99 ? "99+" : n || "");

/** The label of a reader slip's progress for a list cell. */
export function dueText(row) {
  if (!row.due_date) return "";
  const late = row.is_overdue ? daysLate(row.due_date) : 0;
  return late ? `quá ${late} ngày` : "";
}
