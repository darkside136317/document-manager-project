<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { call } from "../lib/api.js";
import Icon from "./Icon.vue";

const BASE = "document_manager.document_manager.api.account";
const open = ref(false);
const rows = ref([]);
const unread = ref(0);
let timer;

async function refresh() {
  try {
    const result = await call(`${BASE}.get_notifications`, { page_length: 10 });
    rows.value = result.rows || [];
    unread.value = result.unread || 0;
  } catch { /* notifications never block the staff workspace */ }
}
async function mark(row) {
  if (!row.read) {
    try { await call(`${BASE}.mark_notifications_read`, { names: [row.name] }, { post: true }); }
    catch { /* navigation still works */ }
  }
  open.value = false;
  if (row.link?.startsWith("/dashboard/")) window.location.assign(row.link);
  else refresh();
}
onMounted(() => { refresh(); timer = window.setInterval(refresh, 30000); });
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <div class="relative">
    <button class="btn btn-ghost btn-icon relative" type="button" aria-label="Thông báo" :aria-expanded="open" @click="open = !open; if (open) refresh()">
      <Icon name="bell" :size="18" /><span v-if="unread" class="absolute -right-1 -top-1 rounded-full bg-danger px-1 text-[10px] text-white">{{ unread > 99 ? '99+' : unread }}</span>
    </button>
    <div v-if="open" class="card absolute right-0 z-40 mt-2 max-h-96 w-80 overflow-y-auto p-2 shadow-pop">
      <p class="m-1 text-sm font-semibold">Thông báo</p>
      <p v-if="!rows.length" class="p-2 text-sm text-ink-muted">Chưa có thông báo.</p>
      <button v-for="row in rows" :key="row.name" class="block w-full rounded p-2 text-left text-sm hover:bg-surface-muted" :class="{ 'font-semibold': !row.read }" type="button" @click="mark(row)">
        {{ row.subject }}
      </button>
    </div>
  </div>
</template>
