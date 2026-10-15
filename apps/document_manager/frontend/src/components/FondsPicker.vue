<script setup>
import { ref, watch } from "vue";
import { api } from "../lib/api.js";
import Icon from "./Icon.vue";
import LinkSelect from "./LinkSelect.vue";

// A list of fonds: chips to remove, a search box to add. Value: [{fonds, fonds_name}].
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  label: { type: String, default: "Phông" },
});
const emit = defineEmits(["update:modelValue"]);
const adding = ref("");

watch(adding, async (value) => {
  if (!value) return;
  if (!props.modelValue.some((row) => row.fonds === value)) {
    let name = value;
    try {
      const hit = (await api.linkSearch("Fonds", value)).find((row) => row.value === value);
      if (hit) name = hit.label;
    } catch {
      /* the code is a usable label */
    }
    emit("update:modelValue", [...props.modelValue, { fonds: value, fonds_name: name }]);
  }
  adding.value = "";
});

const remove = (fonds) => emit("update:modelValue", props.modelValue.filter((row) => row.fonds !== fonds));
</script>

<template>
  <div class="space-y-2">
    <ul v-if="modelValue.length" class="m-0 flex list-none flex-wrap gap-1.5 p-0" :aria-label="label">
      <li v-for="row in modelValue" :key="row.fonds" class="badge badge-info inline-flex items-center gap-1">
        {{ row.fonds_name || row.fonds }}
        <button v-if="!disabled" type="button" class="leading-none" :aria-label="`Bỏ ${row.fonds_name || row.fonds}`" @click="remove(row.fonds)">
          <Icon name="x" :size="12" />
        </button>
      </li>
    </ul>
    <p v-else class="m-0 text-xs text-ink-muted">Chưa chọn phông nào.</p>
    <LinkSelect v-if="!disabled" v-model="adding" doctype="Fonds" :clearable="false" placeholder="Thêm phông…" />
  </div>
</template>
