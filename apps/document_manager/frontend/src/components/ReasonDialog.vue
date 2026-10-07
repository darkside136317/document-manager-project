<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import Icon from "./Icon.vue";

// A dialog that asks for a written reason (turning a request down, for instance) before it acts.
const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Nhập lý do" },
  message: { type: String, default: "" },
  label: { type: String, default: "Lý do" },
  confirmText: { type: String, default: "Đồng ý" },
  danger: { type: Boolean, default: false },
  required: { type: Boolean, default: true },
  busy: { type: Boolean, default: false },
  error: { type: String, default: "" },
});
const emit = defineEmits(["confirm", "cancel"]);

const text = ref("");
const field = ref(null);
const missing = ref(false);

function onKey(event) {
  if (event.key === "Escape") emit("cancel");
}
watch(
  () => props.open,
  async (open) => {
    if (open) {
      text.value = "";
      missing.value = false;
      document.addEventListener("keydown", onKey);
      await nextTick();
      field.value?.focus();
    } else {
      document.removeEventListener("keydown", onKey);
    }
  },
);
onBeforeUnmount(() => document.removeEventListener("keydown", onKey));

function confirm() {
  if (props.required && !text.value.trim()) {
    missing.value = true;
    return;
  }
  emit("confirm", text.value.trim());
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[60] grid place-items-center p-4" role="dialog" aria-modal="true" :aria-label="title">
      <div class="absolute inset-0 bg-black/45" @click="emit('cancel')"></div>
      <section class="card relative w-full max-w-md p-5 shadow-pop">
        <h2 class="m-0 flex items-center gap-2 text-base font-semibold">
          <Icon v-if="danger" name="alert-triangle" class="text-danger" /> {{ title }}
        </h2>
        <p v-if="message" class="mt-3 whitespace-pre-line text-sm text-ink-soft">{{ message }}</p>
        <label class="label mt-4" for="reason-text">{{ label }}<span v-if="required" class="text-danger"> *</span></label>
        <textarea id="reason-text" ref="field" v-model="text" class="input" :class="{ 'is-invalid': missing }" rows="3"></textarea>
        <p v-if="missing" class="mt-1 text-xs text-danger" role="alert">Vui lòng nhập {{ label.toLowerCase() }}.</p>
        <p v-if="error" class="mt-3 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
        <div class="mt-5 flex justify-end gap-2">
          <button class="btn" type="button" :disabled="busy" @click="emit('cancel')">Hủy</button>
          <button class="btn" :class="danger ? 'btn-danger' : 'btn-primary'" type="button" :disabled="busy" @click="confirm">
            <Icon v-if="busy" name="loader" :size="16" spin /> {{ confirmText }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
