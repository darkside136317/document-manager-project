<script setup>
import { computed, ref } from "vue";
import { api } from "../lib/api.js";
import { boot } from "../lib/boot.js";
import { printUrl } from "../lib/reports.js";
import { toast } from "../lib/toast.js";
import ConfirmDialog from "./ConfirmDialog.vue";
import Icon from "./Icon.vue";

// Extra panel of the inventory form: build the lines from the system's figures, complete the check (which locks the
// figures), reopen it, and open the report of it. It acts on the saved record, so unsaved edits are saved first.
const props = defineProps({
  record: { type: Object, required: true },
  meta: { type: Object, required: true },
  dirty: { type: Boolean, default: false },
});
const emit = defineEmits(["changed"]);

const busy = ref("");
const error = ref("");
const confirm = ref(false);

const done = computed(() => props.record.status === "Hoàn thành");
const started = computed(() => props.record.status === "Đang kiểm kê");
const canWrite = props.meta.permissions.write;
const isAdmin = boot.user.roles.includes("Document Admin") || boot.user.roles.includes("System Manager");
const report = computed(() => ({ inventory_check: props.record.name }));

async function act(kind, action, message) {
  busy.value = kind;
  error.value = "";
  try {
    await action(props.record.name);
    toast(message);
    emit("changed");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
    confirm.value = false;
  }
}
</script>

<template>
  <section class="mt-6 space-y-4 border-t border-line pt-5" aria-label="Kiểm kê phông">
    <h3 class="m-0 text-xs font-semibold uppercase tracking-wide text-ink-muted">Kiểm kê</h3>
    <p v-if="done" class="m-0 text-sm text-ink-soft">Đợt kiểm kê đã hoàn thành: số liệu đã khóa. {{ record.total_difference }} phông có chênh lệch giữa sổ sách và thực tế.</p>
    <p v-else-if="started" class="m-0 text-sm text-ink-soft">Nhập số đếm thực tế của từng phông, đánh dấu “Đã kiểm” rồi hoàn thành. Số sổ sách là số liệu của hệ thống tại lúc lập danh sách.</p>
    <p v-else class="m-0 text-sm text-ink-soft">Bấm lập danh sách để lấy số hồ sơ, văn bản và số hộp hiện có của các phông cần kiểm kê.</p>
    <p v-if="dirty && !done" class="m-0 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning" role="status">Có thay đổi chưa lưu. Hãy lưu trước khi dùng các nút bên dưới.</p>
    <p v-if="error" class="m-0 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

    <div class="flex flex-wrap gap-2">
      <button v-if="canWrite && !done" class="btn" type="button" :disabled="Boolean(busy) || dirty" @click="act('populate', api.inventory.populate, started ? 'Đã cập nhật danh sách phông' : 'Đã lập danh sách phông')">
        <Icon :name="busy === 'populate' ? 'loader' : 'refresh-cw'" :size="16" :spin="busy === 'populate'" />
        {{ started ? "Lập lại danh sách (giữ số đã nhập)" : "Lập danh sách phông" }}
      </button>
      <button v-if="canWrite && started" class="btn btn-primary" type="button" :disabled="Boolean(busy) || dirty" @click="confirm = true">
        <Icon name="clipboard-check" :size="16" /> Hoàn thành kiểm kê
      </button>
      <button v-if="done && isAdmin" class="btn" type="button" :disabled="Boolean(busy)" @click="act('reopen', api.inventory.reopen, 'Đã mở lại đợt kiểm kê')">
        <Icon :name="busy === 'reopen' ? 'loader' : 'undo'" :size="16" :spin="busy === 'reopen'" /> Mở lại
      </button>
    </div>

    <div v-if="started || done" class="flex flex-wrap gap-2">
      <RouterLink class="btn" :to="{ path: '/bao-cao/tong-kiem-ke', query: report }"><Icon name="chart-bar" :size="16" /> Xem báo cáo</RouterLink>
      <a class="btn" :href="printUrl('tong-kiem-ke', report)" target="_blank" rel="noopener"><Icon name="printer" :size="16" /> In biên bản</a>
      <a class="btn" :href="printUrl('tong-kiem-ke', report, 'pdf')"><Icon name="file-down" :size="16" /> PDF</a>
    </div>

    <ConfirmDialog
      :open="confirm" :busy="busy === 'complete'" :error="error" title="Hoàn thành kiểm kê?" confirm-text="Hoàn thành"
      message="Sau khi hoàn thành, số liệu kiểm kê bị khóa. Chỉ quản trị viên mới mở lại được."
      @confirm="act('complete', api.inventory.complete, 'Đã hoàn thành đợt kiểm kê')" @cancel="confirm = false"
    />
  </section>
</template>
