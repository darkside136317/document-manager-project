<script setup>
import Icon from "./Icon.vue";

defineProps({
  icon: { type: String, default: "inbox" },
  title: { type: String, required: true },
  text: { type: String, default: "" },
});
</script>

<template>
  <div class="flex flex-col items-center gap-2 px-6 py-14 text-center text-ink-muted">
    <Icon :name="icon" :size="36" class="text-ink-subtle" />
    <p class="m-0 text-base font-medium text-ink">{{ title }}</p>
    <p v-if="text" class="m-0 max-w-sm text-sm">{{ text }}</p>
    <div class="mt-2"><slot /></div>
  </div>
</template>
