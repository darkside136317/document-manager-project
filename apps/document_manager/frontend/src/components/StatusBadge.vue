<script setup>
import { badgeClass } from "../lib/tone.js";

defineProps({ value: { type: String, default: "" } });
</script>

<template>
  <span v-if="value" :class="badgeClass(value)">{{ value }}</span>
</template>
