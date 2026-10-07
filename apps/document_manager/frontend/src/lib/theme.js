import { ref } from "vue";

const KEY = "dm-theme";
export const theme = ref("light");

function stored() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null; // private windows / blocked storage
  }
}

export function applyTheme(value) {
  theme.value = value;
  document.documentElement.setAttribute("data-theme", value);
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* the page works without remembering the choice */
  }
}

export function initTheme() {
  const saved = stored();
  const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved === "dark" || saved === "light" ? saved : dark ? "dark" : "light");
}

export const toggleTheme = () => applyTheme(theme.value === "dark" ? "light" : "dark");
