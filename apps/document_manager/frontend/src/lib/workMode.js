import { ref } from "vue";
import { boot } from "./boot.js";

let saved = "exploitation";
try { saved = sessionStorage.getItem("dm-work-mode") || saved; } catch { /* optional */ }
export const workMode = ref(boot.digitization?.allowed && saved === "digitization" ? "digitization" : "exploitation");

export function setWorkMode(value) {
  workMode.value = boot.digitization?.allowed && value === "digitization" ? "digitization" : "exploitation";
  try { sessionStorage.setItem("dm-work-mode", workMode.value); } catch { /* optional */ }
  window.location.reload();
}
