<script setup>
import { computed } from "vue";
import { formatNumber } from "../lib/format.js";
import Icon from "./Icon.vue";

const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
  capped: { type: Boolean, default: false }, // the count stopped at its ceiling: there are more
});
const emit = defineEmits(["change"]);

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
const from = computed(() => (props.total ? (props.page - 1) * props.pageSize + 1 : 0));
const to = computed(() => Math.min(props.total, props.page * props.pageSize));
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-ink-muted">
    <span>Hiển thị {{ formatNumber(from) }}–{{ formatNumber(to) }} / {{ formatNumber(total) }}{{ capped ? "+" : "" }}</span>
    <div class="flex items-center gap-2">
      <button class="btn btn-icon" type="button" :disabled="page <= 1" aria-label="Trang trước" @click="emit('change', page - 1)">
        <Icon name="chevron-left" :size="16" />
      </button>
      <span>Trang {{ page }} / {{ pages }}</span>
      <button class="btn btn-icon" type="button" :disabled="page >= pages" aria-label="Trang sau" @click="emit('change', page + 1)">
        <Icon name="chevron-right" :size="16" />
      </button>
    </div>
  </div>
</template>
