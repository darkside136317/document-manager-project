<script setup>
import { computed } from "vue";
import { displayValue } from "../lib/format.js";
import { formatSize } from "../lib/upload.js";
import Icon from "./Icon.vue";
import StatusBadge from "./StatusBadge.vue";

// Rows of a registered DocType: one column per list field, the first column is the record's title.
// The server may describe columns the form hides (size, index state): they come in `meta.columns`.
const props = defineProps({
  meta: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  sort: { type: String, default: "" },
  rowKey: { type: String, default: "name" },
});
const emit = defineEmits(["open", "sort"]);

const columns = computed(() =>
  props.meta.columns?.length
    ? props.meta.columns
    : props.meta.list_fields.map((name) => {
        const field = props.meta.fields.find((f) => f.fieldname === name) || {};
        return { fieldname: name, label: field.label || name, fieldtype: field.fieldtype || "Data" };
      }),
);

const isStatus = (column) => column.fieldtype === "Select" && /status$/.test(column.fieldname);
function text(column, value) {
  if (column.fieldname === "file_size_kb") return value ? formatSize(Math.round(Number(value) * 1024)) : "";
  return displayValue(column, value);
}
</script>

<template>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.fieldname" scope="col">
            <button class="inline-flex items-center gap-1 font-semibold uppercase tracking-wide" type="button" @click="emit('sort', column.fieldname)">
              {{ column.label }}
              <span v-if="sort.startsWith(column.fieldname + ' ')" class="text-primary">{{ sort.endsWith('asc') ? '▲' : '▼' }}</span>
            </button>
          </th>
          <th scope="col" class="w-12"><span class="sr-only">Mở</span></th>
        </tr>
      </thead>
      <tbody :class="{ 'opacity-60': loading }">
        <tr v-for="row in rows" :key="row[rowKey]" class="is-clickable" tabindex="0" @click="emit('open', row)" @keydown.enter="emit('open', row)">
          <td v-for="(column, index) in columns" :key="column.fieldname" :class="index === 0 ? 'font-medium' : 'text-ink-soft'">
            <span v-if="column.fieldtype === 'Check'" class="badge" :class="row[column.fieldname] ? 'badge-success' : 'badge-muted'">
              {{ row[column.fieldname] ? "Có" : "Không" }}
            </span>
            <StatusBadge v-else-if="isStatus(column)" :value="row[column.fieldname]" />
            <template v-else>{{ text(column, row[column.fieldname]) }}</template>
          </td>
          <td class="text-right text-ink-subtle"><Icon name="chevron-right" :size="16" /></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
