<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { boot } from "../lib/boot.js";
import { pageTitle } from "../lib/page.js";
import { theme, toggleTheme } from "../lib/theme.js";
import ChangePasswordDialog from "./ChangePasswordDialog.vue";
import Icon from "./Icon.vue";
import SidebarNav from "./SidebarNav.vue";
import ToastHost from "./ToastHost.vue";
import UserMenu from "./UserMenu.vue";

const route = useRoute();
const menuOpen = ref(false);
const passwordOpen = ref(false);
const title = computed(() => pageTitle.value || route.meta.title || "");

watch(() => route.fullPath, () => (menuOpen.value = false));
watch(title, (value) => { document.title = value ? `${value} — ${boot.org}` : boot.org; }, { immediate: true });
</script>

<template>
  <div class="min-h-screen lg:pl-[272px]">
    <div v-if="menuOpen" class="fixed inset-0 z-30 bg-black/50 lg:hidden" @click="menuOpen = false"></div>
    <aside
      class="sidebar fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col transition-transform duration-200 lg:translate-x-0"
      :class="menuOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex items-center gap-3 border-b border-white/10 px-5 py-4">
        <span class="grid h-9 w-9 place-items-center rounded-lg bg-accent text-primary"><Icon name="archive" :size="20" /></span>
        <div class="min-w-0">
          <p class="m-0 truncate text-sm font-semibold text-white">{{ boot.org }}</p>
          <p class="m-0 text-xs text-white/55">Quản lý tài liệu lưu trữ</p>
        </div>
      </div>
      <SidebarNav @navigate="menuOpen = false" />
    </aside>

    <div class="flex min-h-screen flex-col">
      <header class="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5 sm:px-6">
        <button class="btn btn-ghost btn-icon lg:hidden" type="button" aria-label="Mở menu" @click="menuOpen = true">
          <Icon name="menu" />
        </button>
        <h1 class="m-0 min-w-0 flex-1 truncate text-sm font-medium text-ink-muted">{{ title }}</h1>
        <button class="btn btn-ghost btn-icon" type="button" :aria-label="theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'" @click="toggleTheme">
          <Icon :name="theme === 'dark' ? 'sun' : 'moon'" />
        </button>
        <UserMenu @change-password="passwordOpen = true" />
      </header>
      <main class="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 sm:px-6">
        <slot />
      </main>
    </div>

    <ChangePasswordDialog :open="passwordOpen" @close="passwordOpen = false" />
    <ToastHost />
  </div>
</template>

<style scoped>
.sidebar { background: var(--dm-brand-navy, #0a1f35); }
</style>
