<script setup>
import { reactive, watch } from "vue";
import { useRoute } from "vue-router";
import { boot } from "../lib/boot.js";
import { badges } from "../lib/registrations.js";
import Icon from "./Icon.vue";

defineEmits(["navigate"]);
const route = useRoute();
const expanded = reactive({});
// The router lives under /dashboard, so a server route "/dashboard/danh-muc/x" is "/danh-muc/x" to it.
const toPath = (route) => route.replace(/^\/dashboard/, "") || "/";
const containsRoute = (group, path) => group.items.some((item) => {
  const target = toPath(item.route);
  return path === target || (target !== "/" && path.startsWith(`${target}/`));
});
const groupBadge = (group) => group.items.reduce((count, item) => count + Number(badges[item.route] || 0), 0);
function toggleGroup(name) {
  const opening = !expanded[name];
  for (const group of boot.nav) expanded[group.group] = false;
  expanded[name] = opening;
}

watch(() => route.path, (path) => {
  for (const group of boot.nav) {
    expanded[group.group] = containsRoute(group, path);
  }
}, { immediate: true });
</script>

<template>
  <nav class="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3 py-4" aria-label="Điều hướng chính">
    <section v-for="(group, index) in boot.nav" :key="group.group">
      <h2 class="m-0">
        <button type="button" class="nav-group-toggle" :aria-expanded="Boolean(expanded[group.group])" :aria-controls="`nav-group-${index}`" @click="toggleGroup(group.group)">
          <span class="min-w-0 flex-1 truncate text-left">{{ group.group }}</span>
          <span v-if="groupBadge(group)" class="rounded-full bg-accent px-1.5 text-[10px] font-semibold text-primary">{{ groupBadge(group) }}</span>
          <Icon name="chevron-right" :size="14" class="nav-group-chevron" :class="{ 'is-open': expanded[group.group] }" />
        </button>
      </h2>
      <div v-show="expanded[group.group]" :id="`nav-group-${index}`" class="pb-1">
      <RouterLink
        v-for="item in group.items"
        :key="item.route"
        v-slot="{ href, navigate, isActive, isExactActive }"
        :to="toPath(item.route)"
        custom
      >
        <a
          :href="href"
          class="nav-item"
          :class="{ 'is-active': toPath(item.route) === '/' ? isExactActive : isActive }"
          @click="(event) => { navigate(event); $emit('navigate'); }"
        >
          <Icon :name="item.icon" :size="18" />
          <span class="truncate">{{ item.label }}</span>
          <span v-if="badges[item.route]" class="ml-auto rounded-full bg-accent px-2 text-xs font-semibold text-primary" :aria-label="`${badges[item.route]} cần xử lý`">{{ badges[item.route] }}</span>
        </a>
      </RouterLink>
      </div>
    </section>

    <!-- Screens that are still the previous server-rendered pages; they open in the same tab. -->
    <section v-if="boot.legacy.length">
      <h2 class="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-white/45">Đang chuyển sang giao diện mới</h2>
      <details v-for="group in boot.legacy" :key="group.group" class="legacy-group">
        <summary class="nav-item cursor-pointer select-none">
          <Icon name="chevron-right" :size="16" class="legacy-chevron opacity-60" />
          <span class="truncate">{{ group.group }}</span>
        </summary>
        <a v-for="item in group.items" :key="item.href" :href="item.href" class="nav-item ml-5">
          <Icon name="external-link" :size="14" class="opacity-50" />
          <span class="truncate">{{ item.label }}</span>
        </a>
      </details>
    </section>
  </nav>
</template>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.78);
  text-decoration: none;
  font-size: 0.875rem;
  border-left: 3px solid transparent;
  transition: background-color 0.15s, color 0.15s;
}
.nav-group-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.75rem;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.nav-group-toggle:hover { background: rgba(255, 255, 255, 0.07); color: #fff; }
.nav-group-toggle:focus-visible { outline: 2px solid var(--dm-accent); outline-offset: -2px; }
.nav-group-chevron { flex: none; transition: transform 0.15s; }
.nav-group-chevron.is-open { transform: rotate(90deg); }
.nav-item:hover { background: rgba(255, 255, 255, 0.07); color: #fff; }
.legacy-group summary { list-style: none; }
.legacy-group summary::-webkit-details-marker { display: none; }
.legacy-chevron { transition: transform 0.15s; }
.legacy-group[open] .legacy-chevron { transform: rotate(90deg); }
.nav-item.is-active {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  border-left-color: var(--dm-accent);
  font-weight: 600;
}
</style>
