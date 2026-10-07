<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { debounce } from "../lib/format.js";
import Icon from "./Icon.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  doctype: { type: String, required: true },
  filters: { type: Object, default: null },
  disabled: { type: Boolean, default: false },
  invalid: { type: Boolean, default: false },
  clearable: { type: Boolean, default: true },
  placeholder: { type: String, default: "Chọn hoặc gõ để tìm..." },
  inputId: { type: String, default: undefined },
});
const emit = defineEmits(["update:modelValue"]);

const query = ref("");
const label = ref("");
const options = ref([]);
const open = ref(false);
const loading = ref(false);
const active = ref(-1);
let ticket = 0;

const shown = computed(() => (open.value ? query.value : label.value || props.modelValue));

async function search(text) {
  const mine = ++ticket;
  loading.value = true;
  try {
    const rows = await api.linkSearch(props.doctype, text, props.filters);
    if (mine === ticket) {
      options.value = rows;
      active.value = rows.length ? 0 : -1;
    }
  } catch {
    if (mine === ticket) options.value = [];
  } finally {
    if (mine === ticket) loading.value = false;
  }
}
const searchSoon = debounce(search, 250);

async function resolveLabel(value) {
  if (!value) {
    label.value = "";
    return;
  }
  label.value = value;
  try {
    const rows = await api.linkSearch(props.doctype, value, props.filters);
    const hit = rows.find((r) => r.value === value);
    if (hit && props.modelValue === value) label.value = hit.label;
  } catch {
    /* the raw value is still a usable label */
  }
}

watch(() => props.modelValue, (value) => { if (!open.value) resolveLabel(value); }, { immediate: true });

function openList() {
  if (props.disabled) return;
  open.value = true;
  query.value = "";
  search("");
}
function onInput(event) {
  query.value = event.target.value;
  searchSoon(query.value);
}
function choose(option) {
  emit("update:modelValue", option.value);
  label.value = option.label;
  open.value = false;
}
function clear() {
  emit("update:modelValue", "");
  label.value = "";
  open.value = false;
}
function closeSoon() {
  setTimeout(() => (open.value = false), 150); // let a click on an option land first
}
function onKey(event) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    if (!open.value) openList();
    else active.value = Math.min(options.value.length - 1, active.value + 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    active.value = Math.max(0, active.value - 1);
  } else if (event.key === "Enter" && open.value && options.value[active.value]) {
    event.preventDefault();
    choose(options.value[active.value]);
  } else if (event.key === "Escape") {
    open.value = false;
  }
}
onBeforeUnmount(() => searchSoon.cancel());
</script>

<template>
  <div class="relative">
    <input
      :id="inputId"
      class="input pr-16"
      :class="{ 'is-invalid': invalid }"
      type="text"
      autocomplete="off"
      role="combobox"
      :aria-expanded="open"
      :value="shown"
      :placeholder="placeholder"
      :disabled="disabled"
      @focus="openList"
      @input="onInput"
      @blur="closeSoon"
      @keydown="onKey"
    />
    <div class="absolute inset-y-0 right-2 flex items-center gap-1 text-ink-muted">
      <Icon v-if="loading" name="loader" :size="15" spin />
      <button v-if="modelValue && clearable && !disabled" type="button" class="rounded p-1 hover:bg-surface-muted" aria-label="Bỏ chọn" @mousedown.prevent="clear">
        <Icon name="x" :size="14" />
      </button>
      <Icon name="chevron-down" :size="15" />
    </div>
    <ul
      v-if="open"
      class="card absolute z-30 mt-1 max-h-60 w-full overflow-auto py-1 shadow-pop"
      role="listbox"
    >
      <li v-if="!options.length && !loading" class="px-3 py-2 text-sm text-ink-muted">Không có kết quả</li>
      <li
        v-for="(option, index) in options"
        :key="option.value"
        role="option"
        :aria-selected="option.value === modelValue"
        class="cursor-pointer px-3 py-2 text-sm"
        :class="index === active ? 'bg-primary-soft' : ''"
        @mousedown.prevent="choose(option)"
        @mouseenter="active = index"
      >
        <span class="font-medium">{{ option.label }}</span>
        <span v-if="option.description" class="ml-2 text-xs text-ink-muted">{{ option.description }}</span>
      </li>
    </ul>
  </div>
</template>
