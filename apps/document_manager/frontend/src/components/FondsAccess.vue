<script setup>
import { onMounted, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { formatDate } from "../lib/format.js";
import Icon from "./Icon.vue";

// Extra panel of the fonds form: who may use the fonds (its mode, and the reader groups and readers it is granted to).
// Grants are made on the reader group or the reader screens.
const props = defineProps({
  record: { type: Object, required: true },
  meta: { type: Object, required: true },
  dirty: { type: Boolean, default: false },
});

const info = ref(null);
const error = ref("");
const MODES = {
  "Công khai": "Mọi độc giả đã được duyệt đều khai thác được phông này.",
  "Theo cấp phép": "Chỉ các nhóm độc giả và độc giả dưới đây khai thác được phông này.",
  "Nội bộ": "Chỉ cán bộ: phông không mở cho độc giả nào, kể cả khi đã cấp phép.",
};

async function load() {
  if (!props.record.name) return;
  try {
    info.value = await api.fondsAccess(props.record.name);
    error.value = "";
  } catch (e) {
    error.value = e.message;
  }
}
onMounted(load);
watch(() => [props.record.name, props.record.modified], load);
</script>

<template>
  <section class="mt-6 border-t border-line pt-4" aria-label="Độc giả được khai thác phông">
    <h3 class="m-0 mb-2 flex items-center gap-2 text-sm font-semibold"><Icon name="users" :size="16" /> Độc giả được khai thác</h3>
    <p v-if="error" class="m-0 text-sm text-danger" role="alert">{{ error }}</p>
    <template v-else-if="info">
      <p class="m-0 text-sm text-ink-soft">{{ MODES[info.mode] || MODES["Theo cấp phép"] }}</p>
      <template v-if="info.mode !== 'Nội bộ' && info.grants">
        <p v-if="!info.grants.length" class="mb-0 mt-2 text-sm text-ink-muted">Chưa cấp cho nhóm hay độc giả nào. Cấp ở màn hình Nhóm độc giả hoặc Độc giả.</p>
        <ul v-else class="m-0 mt-2 list-none space-y-1 p-0 text-sm">
          <li v-for="g in info.grants" :key="`${g.kind}-${g.name}`" class="flex flex-wrap items-center gap-2">
            <span class="badge" :class="g.kind === 'group' ? 'badge-info' : 'badge-muted'">{{ g.kind === "group" ? "Nhóm" : "Độc giả" }}</span>
            <span class="font-medium">{{ g.label }}</span>
            <span class="text-xs text-ink-muted">{{ g.valid_until ? `đến ${formatDate(g.valid_until)}` : "không thời hạn" }}</span>
            <span v-if="!g.active" class="badge badge-warning">Chưa hoặc hết hiệu lực</span>
          </li>
        </ul>
      </template>
    </template>
  </section>
</template>
