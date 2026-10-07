<script setup>
import { onBeforeUnmount, ref } from "vue";
import { api } from "../lib/api.js";
import { debounce } from "../lib/format.js";

// A free-text field that offers the values of a quick-entry dictionary (frequently typed, identical
// entries). The user may still type anything: the dictionary only saves typing.
const props = defineProps({
  modelValue: { type: String, default: "" },
  dictionary: { type: String, required: true }, // Dictionary Type name
  disabled: { type: Boolean, default: false },
  invalid: { type: Boolean, default: false },
  inputId: { type: String, default: undefined },
});
const emit = defineEmits(["update:modelValue"]);

const options = ref([]);
const open = ref(false);
const active = ref(-1);
let ticket = 0;

async function search(text) {
  const mine = ++ticket;
  try {
    const rows = await api.linkSearch("Quick Entry Dictionary", text, { dictionary_type: props.dictionary, is_active: 1 });
    if (mine !== ticket) return;
    options.value = rows.filter((r) => r.label !== text);
    active.value = -1;
  } catch {
    options.value = [];
  }
}
const searchSoon = debounce(search, 250);
onBeforeUnmount(() => searchSoon.cancel());

function onFocus() {
  if (props.disabled) return;
  open.value = true;
  search(props.modelValue);
}
function onInput(event) {
  emit("update:modelValue", event.target.value);
  open.value = true;
  searchSoon(event.target.value);
}
function choose(option) {
  emit("update:modelValue", option.label);
  open.value = false;
}
function onKey(event) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    active.value = Math.min(options.value.length - 1, active.value + 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    active.value = Math.max(-1, active.value - 1);
  } else if (event.key === "Enter" && open.value && options.value[active.value]) {
    event.preventDefault();
    choose(options.value[active.value]);
  } else if (event.key === "Escape") {
    open.value = false;
  }
}
</script>

<template>
  <div class="relative">
    <input
      :id="inputId"
      class="input"
      :class="{ 'is-invalid': invalid }"
      type="text"
      autocomplete="off"
      role="combobox"
      :aria-expanded="open && options.length > 0"
      :value="modelValue"
      :disabled="disabled"
      @focus="onFocus"
      @input="onInput"
      @blur="() => setTimeout(() => (open = false), 150)"
      @keydown="onKey"
    />
    <ul v-if="open && options.length" class="card absolute z-30 mt-1 max-h-52 w-full overflow-auto py-1 shadow-pop" role="listbox">
      <li
        v-for="(option, index) in options"
        :key="option.value"
        role="option"
        class="cursor-pointer px-3 py-2 text-sm"
        :class="index === active ? 'bg-primary-soft' : ''"
        @mousedown.prevent="choose(option)"
        @mouseenter="active = index"
      >{{ option.label }}</li>
    </ul>
  </div>
</template>
