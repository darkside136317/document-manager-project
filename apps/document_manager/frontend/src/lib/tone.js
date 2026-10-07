// Colour of the badge for the status-like values the archive uses.
const TONES = {
  "Đã hoàn thành": "success",
  "Đã index": "success",
  "Thành công": "success",
  "Hoàn thành": "success",
  "Đang xử lý": "info",
  "Đang chạy": "info",
  "Chờ duyệt": "warning",
  "Chờ lãnh đạo duyệt": "warning",
  "Đã duyệt": "success",
  "Đang sử dụng": "info",
  "Đã giao": "info",
  "Đã trả": "success",
  "Từ chối": "danger",
  "Mới": "warning",
  "Đã xem": "info",
  "Đã phản hồi": "success",
  "Cảnh báo tiêu hủy": "warning",
  "Một phần": "warning",
  Lỗi: "danger",
  "Đã tiêu hủy": "danger",
  "Phát hiện lỗi": "danger",
};

export const toneFor = (value) => TONES[value] || "muted";
export const badgeClass = (value) => `badge badge-${toneFor(value)}`;
