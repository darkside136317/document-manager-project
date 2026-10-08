<script setup>
import { computed } from "vue";
import { filterField, linkFilter, withFilter } from "../lib/reports.js";
import FieldInput from "./FieldInput.vue";
import Icon from "./Icon.vue";

// The filters a report (or an export) declares, drawn with the same inputs as the record forms. A filter that hangs
// on another (the record groups of a fonds) searches inside the other's value and restarts when it changes.
const props = defineProps({
  filters: { type: Array, required: true },
  modelValue: { type: Object, required: true },
  busy: { type: Boolean, default: false },
  submitLabel: { type: String, default: "Xem kết quả" },
  hideSubmit: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue", "submit", "reset"]);

const fields = computed(() => props.filters.map((spec) => ({ spec, field: filterField(spec) })));
const change = (name, value) => emit("update:modelValue", withFilter(props.filters, props.modelValue, name, value));
</script>

<template>
  <form class="space-y-4" @submit.prevent="emit('submit')">
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <FieldInput
        v-for="{ spec, field } in fields"
        :key="spec.fieldname"
        :field="field"
        :model-value="modelValue[spec.fieldname]"
        :link-filters="linkFilter(spec, modelValue)"
        @update:model-value="change(spec.fieldname, $event)"
      />
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button v-if="!hideSubmit" class="btn btn-primary" type="submit" :disabled="busy">
        <Icon :name="busy ? 'loader' : 'search'" :size="16" :spin="busy" /> {{ submitLabel }}
      </button>
      <button class="btn" type="button" @click="emit('reset')">Xóa bộ lọc</button>
      <slot name="actions" />
    </div>
  </form>
</template>
