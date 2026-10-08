<script setup>
import { computed } from "vue";
import { blankRow, selectOptions } from "../lib/doctype.js";
import Icon from "./Icon.vue";
import LinkSelect from "./LinkSelect.vue";

// A child table (rows of a few simple columns) edited as a grid: add a row, change cells, remove a row.
// The server describes the columns (`field.table.columns`) and replaces the whole table on save.
const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const columns = computed(() => props.field.table.columns);
const rows = computed(() => props.modelValue || []);
const editable = computed(() => !props.disabled && !props.field.read_only);

function update(index, name, value) {
  emit("update:modelValue", rows.value.map((row, i) => (i === index ? { ...row, [name]: value } : row)));
}
const add = () => emit("update:modelValue", [...rows.value, blankRow(columns.value)]);
const remove = (index) => emit("update:modelValue", rows.value.filter((_, i) => i !== index));
const numeric = (value) => (value === "" ? null : Number(value));
const cellDisabled = (column) => !editable.value || column.read_only;
// A cell needs room for what it holds: a name to read, a number of a few digits, a note to type.
const widths = { Link: "min-w-[12rem]", Select: "min-w-[8rem]", Int: "min-w-[4.5rem]", Float: "min-w-[5.5rem]", Date: "min-w-[9rem]", Check: "", "Small Text": "min-w-[10rem]", Data: "min-w-[9rem]" };
const cellWidth = (column) => widths[column.fieldtype] ?? "min-w-[8rem]";
</script>

<template>
  <div>
    <span class="label">{{ field.label }}<span v-if="field.reqd" class="text-danger"> *</span></span>
    <div class="table-wrap rounded-md border border-line">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.fieldname" scope="col">{{ column.label }}</th>
            <th v-if="editable" scope="col" class="w-10"><span class="sr-only">Xóa dòng</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="text-center text-ink-muted">Chưa có dòng nào</td>
          </tr>
          <tr v-for="(row, index) in rows" :key="index">
            <td v-for="column in columns" :key="column.fieldname" class="!py-1.5" :class="cellWidth(column)">
              <input
                v-if="column.fieldtype === 'Check'"
                type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" :checked="Boolean(row[column.fieldname])"
                :disabled="cellDisabled(column)" :aria-label="column.label"
                @change="update(index, column.fieldname, $event.target.checked ? 1 : 0)"
              />
              <select
                v-else-if="column.fieldtype === 'Select'"
                class="input" :value="row[column.fieldname] ?? ''" :disabled="cellDisabled(column)" :aria-label="column.label"
                @change="update(index, column.fieldname, $event.target.value)"
              >
                <option v-for="option in selectOptions(column)" :key="option" :value="option">{{ option || "— Chọn —" }}</option>
              </select>
              <LinkSelect
                v-else-if="column.fieldtype === 'Link'"
                :model-value="row[column.fieldname] || ''" :doctype="column.options" :disabled="cellDisabled(column)"
                :clearable="!column.reqd" @update:model-value="update(index, column.fieldname, $event)"
              />
              <input
                v-else-if="column.fieldtype === 'Int' || column.fieldtype === 'Float'"
                class="input" type="number" :step="column.fieldtype === 'Int' ? 1 : 'any'" :value="row[column.fieldname] ?? ''"
                :disabled="cellDisabled(column)" :aria-label="column.label"
                @input="update(index, column.fieldname, numeric($event.target.value))"
              />
              <input
                v-else
                class="input" :type="column.fieldtype === 'Date' ? 'date' : 'text'" :value="row[column.fieldname] ?? ''"
                :disabled="cellDisabled(column)" :aria-label="column.label"
                @input="update(index, column.fieldname, $event.target.value)"
              />
            </td>
            <td v-if="editable" class="text-right !py-1.5">
              <button class="btn btn-ghost btn-icon" type="button" :aria-label="`Xóa dòng ${index + 1}`" @click="remove(index)">
                <Icon name="trash-2" :size="16" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <button v-if="editable" class="btn mt-2" type="button" @click="add"><Icon name="plus" :size="16" /> Thêm dòng</button>
    <p v-if="error" class="mt-1 text-xs text-danger" role="alert">{{ error }}</p>
    <p v-else-if="field.description" class="mt-1 text-xs text-ink-muted">{{ field.description }}</p>
  </div>
</template>
