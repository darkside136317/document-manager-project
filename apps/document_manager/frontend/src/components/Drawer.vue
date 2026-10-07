<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  width: { type: String, default: "560px" },
});
const emit = defineEmits(["close"]);
const panel = ref(null);

function onKey(event) {
  if (event.key === "Escape") emit("close");
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      document.addEventListener("keydown", onKey);
      await nextTick();
      panel.value?.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled])")?.focus();
    } else {
      document.removeEventListener("keydown", onKey);
    }
  },
);
onBeforeUnmount(() => document.removeEventListener("keydown", onKey));
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" :aria-label="title">
      <div class="absolute inset-0 bg-black/45" @click="emit('close')"></div>
      <section ref="panel" class="relative flex h-full max-w-full flex-col bg-surface shadow-pop" :style="{ width }">
        <header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 class="m-0 text-base font-semibold">{{ title }}</h2>
          <button class="btn btn-ghost btn-icon" type="button" aria-label="Đóng" @click="emit('close')"><Icon name="x" /></button>
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4"><slot /></div>
        <footer v-if="$slots.footer" class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-5 py-3">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>
