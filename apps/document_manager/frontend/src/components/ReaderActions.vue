<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../lib/api.js";
import { formatDate } from "../lib/format.js";
import { absoluteLink } from "../lib/registrations.js";
import { toast } from "../lib/toast.js";
import Icon from "./Icon.vue";
import OneTimeLinkDialog from "./OneTimeLinkDialog.vue";
import StatusBadge from "./StatusBadge.vue";

// Extra panel of the reader form: online access (create the account, hand over a set-password link),
// the reader card, and what the reader is doing right now (open and overdue slips, recent slips).
const props = defineProps({ record: { type: Object, required: true }, meta: { type: Object, required: true } });
const emit = defineEmits(["changed"]);

const summary = ref(null);
const busy = ref(false);
const error = ref("");
const link = reactive({ open: false, url: "", user: "" });
const canIssue = props.meta.permissions.write;

async function loadSummary() {
  try {
    summary.value = await api.slips.readerSlips(props.record.name);
  } catch {
    summary.value = null; // the panel is informative: the form works without it
  }
}
onMounted(loadSummary);

async function issue() {
  busy.value = true;
  error.value = "";
  try {
    const result = await api.readerAccess(props.record.name);
    Object.assign(link, { open: true, url: absoluteLink(result.set_password_path), user: result.user });
    if (result.created) {
      toast("Đã tạo tài khoản đăng nhập cho độc giả");
      emit("changed");
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

const slipRoute = (slip) => `/doc-gia/${slip.kind === "usage" ? "phieu-su-dung" : "phieu-sao-chup"}/${encodeURIComponent(slip.name)}`;
</script>

<template>
  <section class="mt-6 space-y-5 border-t border-line pt-5" aria-label="Khai thác của độc giả">
    <div>
      <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Truy cập trực tuyến</h3>
      <p class="mb-2 text-sm text-ink-soft">
        <template v-if="record.user">Tài khoản đăng nhập: <strong>{{ record.user }}</strong>.</template>
        <template v-else>Độc giả chưa có tài khoản đăng nhập{{ record.email ? "" : " (cần có email để cấp)" }}.</template>
      </p>
      <p v-if="error" class="mb-2 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
      <button v-if="canIssue" class="btn" type="button" :disabled="busy || !record.is_active" @click="issue">
        <Icon :name="busy ? 'loader' : 'key-round'" :size="16" :spin="busy" />
        {{ record.user ? "Cấp liên kết đặt mật khẩu mới" : "Tạo tài khoản và cấp liên kết" }}
      </button>
    </div>

    <div v-if="summary">
      <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Khai thác</h3>
      <p class="mb-2 text-sm">
        <span class="badge badge-muted">{{ summary.open }} phiếu đang xử lý</span>
        <span v-if="summary.overdue" class="badge badge-danger ml-1">{{ summary.overdue }} phiếu quá hạn</span>
      </p>
      <ul v-if="summary.slips.length" class="m-0 list-none space-y-1 p-0 text-sm">
        <li v-for="slip in summary.slips" :key="`${slip.kind}-${slip.name}`" class="flex items-center justify-between gap-2">
          <RouterLink :to="slipRoute(slip)" class="font-medium hover:underline">{{ slip.name }}</RouterLink>
          <span class="text-ink-muted">{{ formatDate(slip.request_date) }}</span>
          <StatusBadge :value="slip.workflow_state" />
        </li>
      </ul>
      <p v-else class="m-0 text-sm text-ink-muted">Độc giả chưa có phiếu nào.</p>
      <div v-if="summary.print.card" class="mt-3 flex gap-2">
        <a class="btn" :href="summary.print.card.view" target="_blank" rel="noopener"><Icon name="printer" :size="16" /> In thẻ độc giả</a>
        <a class="btn" :href="summary.print.card.pdf" target="_blank" rel="noopener"><Icon name="download" :size="16" /> PDF</a>
      </div>
    </div>
    <OneTimeLinkDialog :open="link.open" :url="link.url" :user="link.user" @close="link.open = false" />
  </section>
</template>
