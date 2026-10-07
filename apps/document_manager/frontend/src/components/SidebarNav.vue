<script setup>
import { boot } from "../lib/boot.js";
import Icon from "./Icon.vue";

defineEmits(["navigate"]);
// The router lives under /dashboard, so a server route "/dashboard/danh-muc/x" is "/danh-muc/x" to it.
const toPath = (route) => route.replace(/^\/dashboard/, "") || "/";
</script>

<template>
  <nav class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" aria-label="Điều hướng chính">
    <section v-for="group in boot.nav" :key="group.group">
      <h2 class="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-white/45">{{ group.group }}</h2>
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
        </a>
      </RouterLink>
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
