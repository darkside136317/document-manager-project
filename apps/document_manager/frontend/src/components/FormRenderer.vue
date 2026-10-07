<script setup>
import { isVisible } from "../lib/doctype.js";
import FieldInput from "./FieldInput.vue";

// Draws a form from the layout the server derived from the DocType (sections of columns).
// The record is edited in place (v-model on a reactive object).
const props = defineProps({
  meta: { type: Object, required: true },
  record: { type: Object, required: true },
  errors: { type: Object, default: () => ({}) },
  editing: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
  linkFilters: { type: Function, default: () => null },
});

const byName = (name) => props.meta.fields.find((f) => f.fieldname === name);
// The name of a record built from one of its fields is fixed once the record exists.
const locked = (field) => props.readOnly || (props.editing && field.fieldname === props.meta.name_field);
// Stacked: every column of a section one under the other, which suits a narrow drawer.
// Fields and sections whose `depends_on` is not met stay out of the form.
const stacked = (section) => section.columns.flat().map(byName).filter((f) => f && isVisible(f.depends_on, props.record));
const shown = (section) => isVisible(section.depends_on, props.record) && stacked(section).length > 0;
</script>

<template>
  <form class="space-y-6" novalidate @submit.prevent>
    <section v-for="(section, index) in meta.layout.filter(shown)" :key="index">
      <h3 v-if="section.title" class="mb-3 border-b border-line pb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {{ section.title }}
      </h3>
      <div class="space-y-4">
        <FieldInput
          v-for="field in stacked(section)"
          :key="field.fieldname"
          :field="field"
          :model-value="record[field.fieldname]"
          :read-only="locked(field)"
          :error="errors[field.fieldname] || ''"
          :link-filters="linkFilters(field)"
          @update:model-value="record[field.fieldname] = $event"
        />
      </div>
    </section>
  </form>
</template>
