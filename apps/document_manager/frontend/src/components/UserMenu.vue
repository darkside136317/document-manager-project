<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { call } from "../lib/api.js";
import { boot, initials } from "../lib/boot.js";
import Icon from "./Icon.vue";

const emit = defineEmits(["change-password"]);
const open = ref(false);
const root = ref(null);

function onDocumentClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false;
}
onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));

async function logout() {
  try {
    await call("logout", {}, { post: true });
  } finally {
    window.location.assign("/login");
  }
}
</script>

<template>
  <div ref="root" class="relative">
    <button class="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-muted" type="button" :aria-expanded="open" aria-haspopup="menu" @click="open = !open">
      <span class="grid h-8 w-8 place-items-center rounded-full bg-primary text-xs font-semibold text-white">{{ initials(boot.user.full_name) }}</span>
      <span class="hidden max-w-[160px] truncate text-sm font-medium sm:block">{{ boot.user.full_name }}</span>
      <Icon name="chevron-down" :size="14" class="text-ink-muted" />
    </button>
    <div v-if="open" class="card absolute right-0 z-40 mt-2 w-64 py-1 shadow-pop" role="menu">
      <div class="border-b border-line px-4 py-3">
        <p class="m-0 truncate text-sm font-semibold">{{ boot.user.full_name }}</p>
        <p class="m-0 truncate text-xs text-ink-muted">{{ boot.user.name }}</p>
      </div>
      <button class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-surface-muted" type="button" role="menuitem" @click="open = false; emit('change-password')">
        <Icon name="key-round" :size="16" /> Đổi mật khẩu
      </button>
      <a class="flex items-center gap-2 px-4 py-2 text-sm text-ink no-underline hover:bg-surface-muted" href="/portal" role="menuitem">
        <Icon name="external-link" :size="16" /> Giao diện độc giả
      </a>
      <button class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-danger hover:bg-surface-muted" type="button" role="menuitem" @click="logout">
        <Icon name="log-out" :size="16" /> Đăng xuất
      </button>
    </div>
  </div>
</template>
