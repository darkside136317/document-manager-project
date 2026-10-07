<script setup>
import { computed } from "vue";
import { iconFor } from "../lib/icons.js";

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
  spin: { type: Boolean, default: false },
});
const component = computed(() => iconFor(props.name));
</script>

<template>
  <component :is="component" :size="size" :class="{ 'animate-spin': spin }" aria-hidden="true" />
</template>
