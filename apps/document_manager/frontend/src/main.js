import { createApp } from "vue";
import App from "./App.vue";
import { initTheme } from "./lib/theme.js";
import { createAppRouter } from "./router.js";
import "./styles/app.css";

initTheme();
createApp(App).use(createAppRouter()).mount("#app");
