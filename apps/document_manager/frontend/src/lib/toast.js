import { reactive } from "vue";

export const toasts = reactive([]);
let seq = 0;

export function toast(message, kind = "success", timeout = 4000) {
  const item = { id: ++seq, message, kind };
  toasts.push(item);
  if (timeout) setTimeout(() => dismiss(item.id), timeout);
  return item.id;
}

export function dismiss(id) {
  const index = toasts.findIndex((t) => t.id === id);
  if (index >= 0) toasts.splice(index, 1);
}

export const toastError = (message) => toast(message, "error", 7000);
