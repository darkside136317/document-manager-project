<script setup>
import { computed } from "vue";

// The fields of one level to take into an export or an import: one checkbox each. The key fields (the code and the
// title that identify a record) are always taken, so they are shown ticked and locked. `found` limits the list to
// what an uploaded file contains and shows how many records carry each field.
const props = defineProps({
  level: { type: Object, required: true },
  chosen: { type: Object, required: true },
  found: { type: Object, default: null },
});
const emit = defineEmits(["toggle", "all", "none"]);

const fields = computed(() => props.level.fields.filter((f) => !props.found || f.fieldname in props.found));
// two fields may share a label ("Trạng thái" of the file and of its disposal): tell them apart by their name
const labels = computed(() => {
  const seen = {};
  for (const f of fields.value) seen[f.label] = (seen[f.label] || 0) + 1;
  return Object.fromEntries(fields.value.map((f) => [f.fieldname, seen[f.label] > 1 ? `${f.label} (${f.fieldname})` : f.label]));
});
const count = computed(() => fields.value.filter((f) => props.chosen.has(f.fieldname)).length);
</script>

<template>
  <fieldset class="rounded-lg border border-line p-4">
    <legend class="flex items-center gap-3 px-2 text-sm font-semibold">
      {{ level.label }}
      <span class="badge badge-muted">{{ count }} / {{ fields.length }} trường</span>
    </legend>
    <div class="mb-3 flex gap-3 text-sm">
      <button class="text-primary hover:underline" type="button" @click="emit('all', level)">Chọn tất cả</button>
      <button class="text-primary hover:underline" type="button" @click="emit('none', level)">Bỏ chọn</button>
    </div>
    <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
      <label v-for="field in fields" :key="field.fieldname" class="flex cursor-pointer items-center gap-2 py-1 text-sm" :class="{ 'cursor-not-allowed text-ink-muted': field.key }">
        <input
          type="checkbox"
          class="h-4 w-4 accent-[var(--dm-primary)]"
          :checked="chosen.has(field.fieldname)"
          :disabled="field.key"
          @change="emit('toggle', level, field.fieldname)"
        />
        <span>{{ labels[field.fieldname] }}</span>
        <span v-if="field.key" class="text-xs text-ink-subtle">(khóa)</span>
        <span v-else-if="found" class="text-xs text-ink-subtle">{{ found[field.fieldname] }}</span>
      </label>
    </div>
  </fieldset>
</template>
