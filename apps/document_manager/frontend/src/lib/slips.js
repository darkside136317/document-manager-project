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

const MAIN_ACTIONS = ["Duyệt", "Giao tài liệu", "Nhận trả", "Hoàn thành", "Gửi duyệt"];
const DANGER_ACTIONS = ["Từ chối", "Hủy phiếu"];

/** How a workflow action looks as a button: primary (the usual next step), danger (turns the slip down), plain.
 *  "Chuyển lãnh đạo" is the usual next step only when the officer cannot approve the slip themselves. */
export function actionStyle(action, actions = []) {
  if (MAIN_ACTIONS.includes(action)) return "btn-primary";
  if (action === "Chuyển lãnh đạo" && !actions.includes("Duyệt")) return "btn-primary";
  if (DANGER_ACTIONS.includes(action)) return "btn-danger";
  return "";
}

/** The usual next step first, the others after it, the ones that turn the slip down last. */
export function sortActions(actions = []) {
  const rank = (a) => ({ "btn-primary": 0, "": 1, "btn-danger": 2 })[actionStyle(a, actions)];
  return [...actions].sort((a, b) => rank(a) - rank(b));
}

/** One sentence under the actions: what the officer is expected to do now, and why a button is missing. */
export function actionHint(slip) {
  const actions = slip?.actions || [];
  if (slip?.state === "Chờ duyệt" && actions.includes("Chuyển lãnh đạo") && !actions.includes("Duyệt")) {
    return "Phiếu có hồ sơ, văn bản cần lãnh đạo duyệt (theo mức độ mật hoặc quy định của nhóm độc giả): quyết định từng dòng rồi bấm Chuyển lãnh đạo.";
  }
  if (actions.includes("Duyệt")) return "Dòng chưa quyết định sẽ được duyệt cùng phiếu; dòng từ chối cần ghi lý do. Từ chối cả phiếu khi không duyệt được dòng nào.";
  if (actions.includes("Giao tài liệu")) return "In phiếu lấy tài liệu để lấy hồ sơ trong kho, rồi bấm Giao tài liệu khi độc giả nhận. Hạn trả tính từ hôm nay.";
  if (actions.includes("Hoàn thành")) return "Bấm Hoàn thành khi đã sao chụp xong và giao bản sao cho độc giả.";
  return "";
}

/** Set every row to approved (rows turned down lose their reason), or back to undecided. */
export function decideAll(items, status) {
  for (const item of items) {
    item.item_status = status;
    if (status !== "Từ chối") item.decision_note = "";
  }
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
