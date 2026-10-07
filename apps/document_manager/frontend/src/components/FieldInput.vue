<script setup>
import { computed } from "vue";
import { selectOptions } from "../lib/doctype.js";
import LinkSelect from "./LinkSelect.vue";
import RichText from "./RichText.vue";

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { default: "" },
  readOnly: { type: Boolean, default: false },
  error: { type: String, default: "" },
  linkFilters: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue"]);

const id = computed(() => `f-${props.field.fieldname}`);
const disabled = computed(() => props.readOnly || props.field.read_only);
const invalid = computed(() => Boolean(props.error));
const inputType = computed(() => {
  const { fieldtype, options } = props.field;
  if (fieldtype === "Int" || fieldtype === "Float") return "number";
  if (fieldtype === "Date") return "date";
  if (fieldtype === "Datetime") return "datetime-local";
  if (options === "Email") return "email";
  if (options === "Phone") return "tel";
  if (options === "URL") return "url";
  return "text";
});
const multiline = computed(() => ["Small Text", "Text", "Long Text"].includes(props.field.fieldtype));

function onNumber(event) {
  const raw = event.target.value;
  emit("update:modelValue", raw === "" ? null : Number(raw));
}
const datetimeValue = computed(() => String(props.modelValue || "").replace(" ", "T").slice(0, 16));
</script>

<template>
  <div>
    <label v-if="field.fieldtype !== 'Check'" :for="id" class="label">
      {{ field.label }}<span v-if="field.reqd" class="text-danger"> *</span>
    </label>

    <label v-if="field.fieldtype === 'Check'" :for="id" class="flex cursor-pointer items-center gap-2 py-2 text-sm font-medium">
      <input
        :id="id"
        type="checkbox"
        class="h-4 w-4 accent-[var(--dm-primary)]"
        :checked="Boolean(modelValue)"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.checked ? 1 : 0)"
      />
      {{ field.label }}
    </label>

    <select
      v-else-if="field.fieldtype === 'Select'"
      :id="id"
      class="input"
      :class="{ 'is-invalid': invalid }"
      :value="modelValue ?? ''"
      :disabled="disabled"
      @change="emit('update:modelValue', $event.target.value)"
    >
      <option v-for="option in selectOptions(field)" :key="option" :value="option">{{ option || "— Chọn —" }}</option>
    </select>

    <LinkSelect
      v-else-if="field.fieldtype === 'Link'"
      :input-id="id"
      :model-value="modelValue || ''"
      :doctype="field.options"
      :filters="linkFilters"
      :disabled="disabled"
      :invalid="invalid"
      :clearable="!field.reqd"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <RichText
      v-else-if="field.fieldtype === 'Text Editor'"
      :input-id="id"
      :model-value="modelValue || ''"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <textarea
      v-else-if="multiline"
      :id="id"
      class="input"
      :class="{ 'is-invalid': invalid }"
      :value="modelValue ?? ''"
      :disabled="disabled"
      rows="3"
      @input="emit('update:modelValue', $event.target.value)"
    ></textarea>

    <input
      v-else-if="field.fieldtype === 'Int' || field.fieldtype === 'Float'"
      :id="id"
      class="input"
      :class="{ 'is-invalid': invalid }"
      type="number"
      :step="field.fieldtype === 'Int' ? 1 : 'any'"
      :value="modelValue ?? ''"
      :disabled="disabled"
      @input="onNumber"
    />

    <input
      v-else-if="field.fieldtype === 'Datetime'"
      :id="id"
      class="input"
      :class="{ 'is-invalid': invalid }"
      type="datetime-local"
      :value="datetimeValue"
      :disabled="disabled"
      @input="emit('update:modelValue', $event.target.value.replace('T', ' '))"
    />

    <input
      v-else
      :id="id"
      class="input"
      :class="{ 'is-invalid': invalid }"
      :type="inputType"
      :value="modelValue ?? ''"
      :disabled="disabled"
      :autocomplete="inputType === 'email' ? 'email' : 'off'"
      @input="emit('update:modelValue', $event.target.value)"
    />

    <p v-if="error" class="mt-1 text-xs text-danger" role="alert">{{ error }}</p>
    <p v-else-if="field.description" class="mt-1 text-xs text-ink-muted">{{ field.description }}</p>
  </div>
</template>
