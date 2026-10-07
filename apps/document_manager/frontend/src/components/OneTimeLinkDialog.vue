<script setup>
import { ref, watch } from "vue";
import { toastError } from "../lib/toast.js";
import Icon from "./Icon.vue";

// Shows a one-time set-password link once, for the officer to hand to the reader (the site sends no e-mail).
const props = defineProps({
  open: { type: Boolean, default: false },
  url: { type: String, default: "" },
  user: { type: String, default: "" },
});
const emit = defineEmits(["close"]);
const copied = ref(false);

watch(() => props.open, (open) => { if (open) copied.value = false; });

async function copy() {
  try {
    await navigator.clipboard.writeText(props.url);
    copied.value = true;
  } catch {
    toastError("Không sao chép tự động được. Hãy chọn và sao chép liên kết thủ công.");
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-[60] grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="Liên kết đặt mật khẩu">
      <div class="absolute inset-0 bg-black/45" @click="emit('close')"></div>
      <section class="card relative w-full max-w-lg p-5 shadow-pop">
        <h2 class="m-0 flex items-center gap-2 text-base font-semibold"><Icon name="key-round" class="text-accent" /> Liên kết đặt mật khẩu</h2>
        <p class="mt-3 text-sm text-ink-soft">
          Gửi liên kết này cho <strong>{{ user }}</strong>. Liên kết chỉ dùng được một lần, hết hạn sau một thời gian
          và <strong>không được lưu lại</strong>: đóng cửa sổ này rồi vẫn có thể cấp liên kết mới.
        </p>
        <div class="mt-3 flex gap-2">
          <input class="input font-mono text-xs" :value="url" readonly aria-label="Liên kết đặt mật khẩu" @focus="$event.target.select()" />
          <button class="btn whitespace-nowrap" type="button" @click="copy"><Icon :name="copied ? 'check' : 'copy'" :size="16" /> {{ copied ? "Đã chép" : "Sao chép" }}</button>
        </div>
        <div class="mt-5 flex justify-end"><button class="btn btn-primary" type="button" @click="emit('close')">Đã chuyển cho người dùng</button></div>
      </section>
    </div>
  </Teleport>
</template>
