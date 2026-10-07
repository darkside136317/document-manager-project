<script setup>
import { onBeforeUnmount, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Xác nhận" },
  message: { type: String, default: "" },
  error: { type: String, default: "" },
  confirmText: { type: String, default: "Đồng ý" },
  danger: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
});
const emit = defineEmits(["confirm", "cancel"]);

function onKey(event) {
  if (event.key === "Escape") emit("cancel");
}
watch(
  () => props.open,
  (open) => (open ? document.addEventListener("keydown", onKey) : document.removeEventListener("keydown", onKey)),
);
onBeforeUnmount(() => document.removeEventListener("keydown", onKey));
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[60] grid place-items-center p-4" role="alertdialog" aria-modal="true" :aria-label="title">
      <div class="absolute inset-0 bg-black/45" @click="emit('cancel')"></div>
      <section class="card relative w-full max-w-md p-5 shadow-pop">
        <h2 class="m-0 flex items-center gap-2 text-base font-semibold">
          <Icon v-if="danger" name="alert-triangle" class="text-danger" /> {{ title }}
        </h2>
        <p class="mt-3 whitespace-pre-line text-sm text-ink-soft">{{ message }}</p>
        <p v-if="error" class="mt-3 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
        <div class="mt-5 flex justify-end gap-2">
          <button class="btn" type="button" :disabled="busy" @click="emit('cancel')">Hủy</button>
          <button class="btn" :class="danger ? 'btn-danger' : 'btn-primary'" type="button" :disabled="busy" @click="emit('confirm')">
            <Icon v-if="busy" name="loader" :size="16" spin /> {{ confirmText }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
