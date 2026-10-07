export function formatDate(value) {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  return match ? `${match[3]}/${match[2]}/${match[1]}` : String(value);
}

export function formatDateTime(value) {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(value));
  return match ? `${match[3]}/${match[2]}/${match[1]} ${match[4]}:${match[5]}` : formatDate(value);
}

export function formatNumber(value) {
  return new Intl.NumberFormat("vi-VN").format(Number(value) || 0);
}

export function truncate(text, length = 80) {
  const value = String(text ?? "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

/** What a list cell shows for a value of the given field. */
export function displayValue(field, value) {
  if (value === null || value === undefined || value === "") return "";
  switch (field.fieldtype) {
    case "Date":
      return formatDate(value);
    case "Datetime":
      return formatDateTime(value);
    case "Check":
      return value ? "Có" : "Không";
    case "Int":
    case "Float":
      return formatNumber(value);
    case "Small Text":
    case "Text":
    case "Long Text":
    case "Text Editor":
      return truncate(value, 90);
    default:
      return String(value);
  }
}

export function debounce(fn, wait = 300) {
  let timer = null;
  const debounced = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  debounced.cancel = () => clearTimeout(timer);
  return debounced;
}
