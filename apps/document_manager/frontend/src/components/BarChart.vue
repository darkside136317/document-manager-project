<script setup>
import { computed } from "vue";
import { formatNumber } from "../lib/format.js";
import { barWidths } from "../lib/reports.js";

// A horizontal bar chart of one series, drawn with plain elements (no chart library): the labels and values stay
// readable text, so it prints and works with a screen reader.
const props = defineProps({ chart: { type: Object, required: true } });
const values = computed(() => props.chart.datasets?.[0]?.values || []);
const widths = computed(() => barWidths(values.value));
const series = computed(() => props.chart.datasets?.[0]?.name || "");
</script>

<template>
  <figure class="m-0">
    <figcaption class="mb-3 text-sm font-semibold">{{ chart.title }}</figcaption>
    <ul class="m-0 list-none space-y-2 p-0" role="list">
      <li v-for="(label, index) in chart.labels" :key="`${index}-${label}`" class="grid grid-cols-[minmax(7rem,14rem)_1fr_auto] items-center gap-3 text-sm">
        <span class="truncate text-ink-soft" :title="label">{{ label }}</span>
        <span class="h-3 rounded-full bg-surface-muted" aria-hidden="true">
          <span class="block h-3 rounded-full bg-primary" :style="{ width: `${widths[index]}%`, minWidth: values[index] ? '4px' : '0' }"></span>
        </span>
        <span class="tabular-nums font-medium" :aria-label="`${label}: ${values[index]} ${series}`">{{ formatNumber(values[index]) }}</span>
      </li>
    </ul>
  </figure>
</template>
