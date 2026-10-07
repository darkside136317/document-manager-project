<script setup>
import { dismiss, toasts } from "../lib/toast.js";
import Icon from "./Icon.vue";
</script>

<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
    <div
      v-for="item in toasts"
      :key="item.id"
      class="card pointer-events-auto flex items-start gap-3 px-4 py-3 shadow-pop"
      :class="item.kind === 'error' ? 'border-danger' : 'border-success'"
      role="status"
    >
      <Icon :name="item.kind === 'error' ? 'alert-triangle' : 'circle-check'" :class="item.kind === 'error' ? 'text-danger' : 'text-success'" />
      <p class="m-0 flex-1 whitespace-pre-line text-sm">{{ item.message }}</p>
      <button class="btn btn-ghost btn-icon !min-h-0 !p-1" type="button" aria-label="Đóng thông báo" @click="dismiss(item.id)">
        <Icon name="x" :size="16" />
      </button>
    </div>
  </div>
</template>
