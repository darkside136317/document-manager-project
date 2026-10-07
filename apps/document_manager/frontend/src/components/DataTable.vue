<script setup>
import { displayValue } from "../lib/format.js";
import Icon from "./Icon.vue";

// Rows of a registered DocType: one column per list field, first column is the record's title.
defineProps({
  meta: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  sort: { type: String, default: "" },
});
const emit = defineEmits(["open", "sort"]);
</script>

<template>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="name in meta.list_fields" :key="name" scope="col">
            <button class="inline-flex items-center gap-1 font-semibold uppercase tracking-wide" type="button" @click="emit('sort', name)">
              {{ meta.fields.find((f) => f.fieldname === name)?.label || name }}
              <span v-if="sort.startsWith(name + ' ')" class="text-primary">{{ sort.endsWith('asc') ? '▲' : '▼' }}</span>
            </button>
          </th>
          <th scope="col" class="w-12"><span class="sr-only">Mở</span></th>
        </tr>
      </thead>
      <tbody :class="{ 'opacity-60': loading }">
        <tr v-for="row in rows" :key="row.name" class="is-clickable" tabindex="0" @click="emit('open', row)" @keydown.enter="emit('open', row)">
          <td v-for="(name, index) in meta.list_fields" :key="name" :class="index === 0 ? 'font-medium' : 'text-ink-soft'">
            <span v-if="meta.fields.find((f) => f.fieldname === name)?.fieldtype === 'Check'" class="badge" :class="row[name] ? 'badge-success' : 'badge-muted'">
              {{ row[name] ? "Có" : "Không" }}
            </span>
            <template v-else>{{ displayValue(meta.fields.find((f) => f.fieldname === name) || {}, row[name]) }}</template>
          </td>
          <td class="text-right text-ink-subtle"><Icon name="chevron-right" :size="16" /></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
