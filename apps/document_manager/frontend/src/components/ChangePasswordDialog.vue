<script setup>
import { reactive, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { toast } from "../lib/toast.js";
import Drawer from "./Drawer.vue";
import Icon from "./Icon.vue";

const props = defineProps({ open: { type: Boolean, default: false } });
const emit = defineEmits(["close"]);

const form = reactive({ old: "", next: "", confirm: "" });
const error = ref("");
const busy = ref(false);

watch(() => props.open, (open) => {
  if (open) {
    Object.assign(form, { old: "", next: "", confirm: "" });
    error.value = "";
  }
});

async function submit() {
  error.value = "";
  if (!form.old || !form.next) return (error.value = "Hãy nhập mật khẩu hiện tại và mật khẩu mới.");
  if (form.next.length < 8) return (error.value = "Mật khẩu mới phải có ít nhất 8 ký tự.");
  if (form.next === form.old) return (error.value = "Mật khẩu mới phải khác mật khẩu hiện tại.");
  if (form.next !== form.confirm) return (error.value = "Mật khẩu xác nhận không khớp.");
  busy.value = true;
  try {
    await api.changePassword(form.old, form.next);
    toast("Đã đổi mật khẩu");
    emit("close");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Drawer :open="open" title="Đổi mật khẩu" width="440px" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <p v-if="error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
      <div>
        <label class="label" for="pw-old">Mật khẩu hiện tại</label>
        <input id="pw-old" v-model="form.old" class="input" type="password" autocomplete="current-password" />
      </div>
      <div>
        <label class="label" for="pw-new">Mật khẩu mới</label>
        <input id="pw-new" v-model="form.next" class="input" type="password" autocomplete="new-password" />
        <p class="mt-1 text-xs text-ink-muted">Tối thiểu 8 ký tự, nên kết hợp chữ hoa, chữ thường, số và ký hiệu.</p>
      </div>
      <div>
        <label class="label" for="pw-confirm">Nhập lại mật khẩu mới</label>
        <input id="pw-confirm" v-model="form.confirm" class="input" type="password" autocomplete="new-password" />
      </div>
      <button class="hidden" type="submit">Đổi mật khẩu</button>
    </form>
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">Hủy</button>
      <button class="btn btn-primary" type="button" :disabled="busy" @click="submit">
        <Icon v-if="busy" name="loader" :size="16" spin /> Đổi mật khẩu
      </button>
    </template>
  </Drawer>
</template>
