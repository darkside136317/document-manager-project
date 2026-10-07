<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import ReasonDialog from "../components/ReasonDialog.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { formatDate, formatDateTime } from "../lib/format.js";
import { pageTitle } from "../lib/page.js";
import { refreshBadges } from "../lib/registrations.js";
import {
  actionStyle, approvedCount, CONDITIONS, confirmText, daysLate, decisionsFrom, kindOf, needsConfirm, needsReason,
  rejectedWithoutReason,
} from "../lib/slips.js";
import { toast, toastError } from "../lib/toast.js";

// One slip for the reading room and the leaders: who asked, what, where it stands, what can be done next.
// Decisions on single items, the workflow actions, the return with the condition of each item, renewal, print.
const props = defineProps({ kind: { type: String, required: true }, name: { type: String, required: true } });
const router = useRouter();

const info = computed(() => kindOf(props.kind));
const slip = ref(null);
const items = ref([]); // local copy: the officer edits decisions here and saves them in one go
const loading = ref(true);
const error = ref("");
const busy = ref(false);
const dialog = reactive({ type: "", action: "", error: "", conditions: {} });

const dirty = computed(() => JSON.stringify(decisionsFrom(items.value)) !== original.value);
const original = ref("[]");

function assign(data) {
  slip.value = data;
  items.value = data.items.map((i) => ({ ...i }));
  original.value = JSON.stringify(decisionsFrom(items.value));
  pageTitle.value = `${info.value.label} ${data.name}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    assign(await api.slips.get(props.kind, props.name));
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(() => [props.kind, props.name], load);

const overdueDays = computed(() => (slip.value?.is_overdue ? daysLate(slip.value.due_date) : 0));
const canDecide = computed(() => Boolean(slip.value?.can.decide_items));
const closeDialog = () => Object.assign(dialog, { type: "", action: "", error: "", conditions: {} });
const listRoute = computed(() => info.value.route);

async function done(message, next) {
  if (next) assign(next);
  else await load();
  toast(message);
  refreshBadges(api.slips.badges);
}

async function saveDecisions() {
  const bad = rejectedWithoutReason(items.value);
  if (bad.length) {
    toastError("Hãy nhập lý do cho các dòng bị từ chối.");
    return false;
  }
  busy.value = true;
  try {
    assign(await api.slips.decideItems(props.kind, props.name, decisionsFrom(items.value)));
    toast("Đã lưu quyết định duyệt");
    return true;
  } catch (e) {
    toastError(e.message);
    return false;
  } finally {
    busy.value = false;
  }
}

async function perform(action, text) {
  busy.value = true;
  dialog.error = "";
  try {
    if (dirty.value && canDecide.value && !(await saveDecisions())) return;
    await api.requests.action(slip.value.doctype, slip.value.name, action, text);
    closeDialog();
    await done(`${action}: đã thực hiện`);
  } catch (e) {
    dialog.error = e.message;
    if (!dialog.type) toastError(e.message);
  } finally {
    busy.value = false;
  }
}

function run(action) {
  dialog.error = "";
  if (action === "Nhận trả") {
    dialog.conditions = Object.fromEntries(items.value.filter((i) => i.item_status === "Đã giao").map((i) => [i.row, "Tốt"]));
    return Object.assign(dialog, { type: "return", action });
  }
  if (needsReason(action)) return Object.assign(dialog, { type: "reason", action });
  if (needsConfirm(action)) return Object.assign(dialog, { type: "confirm", action });
  return perform(action);
}

async function receiveReturn() {
  busy.value = true;
  dialog.error = "";
  try {
    const next = await api.slips.receiveReturn(slip.value.name, JSON.stringify(dialog.conditions));
    closeDialog();
    await done("Đã nhận trả tài liệu", next);
  } catch (e) {
    dialog.error = e.message;
  } finally {
    busy.value = false;
  }
}

async function renew() {
  busy.value = true;
  dialog.error = "";
  try {
    const next = await api.slips.renew(slip.value.name);
    closeDialog();
    await done(`Đã gia hạn đến ${formatDate(next.due_date)}`, next);
  } catch (e) {
    dialog.error = e.message;
  } finally {
    busy.value = false;
  }
}

async function removeDraft() {
  busy.value = true;
  try {
    await api.slips.deleteDraft(props.kind, props.name);
    toast("Đã xóa phiếu nháp");
    refreshBadges(api.slips.badges);
    router.replace(listRoute.value);
  } catch (e) {
    dialog.error = e.message;
  } finally {
    busy.value = false;
  }
}

const setDecision = (item, status) => {
  item.item_status = item.item_status === status ? "Chờ duyệt" : status;
  if (item.item_status !== "Từ chối") item.decision_note = item.item_status === "Đã duyệt" ? item.decision_note : "";
};
const printLinks = computed(() => Object.entries(slip.value?.print || {}));
const printLabel = (kind) => ({ standard: "Phiếu", pickup: "Phiếu lấy tài liệu" })[kind] || kind;
const reviewLabel = computed(() => (slip.value?.state === "Chờ lãnh đạo duyệt" ? "Lãnh đạo duyệt từng dòng" : "Duyệt từng hồ sơ, văn bản"));
</script>

<template>
  <div v-if="loading && !slip" class="flex items-center gap-2 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
  <EmptyState v-else-if="error" icon="alert-triangle" title="Không mở được phiếu" :text="error">
    <RouterLink class="btn" :to="listRoute">Về danh sách</RouterLink>
  </EmptyState>

  <template v-else-if="slip">
    <nav class="mb-3 text-sm text-ink-muted" aria-label="Đường dẫn">
      <RouterLink :to="listRoute" class="hover:underline">{{ info.label }}</RouterLink> › <span>{{ slip.name }}</span>
    </nav>

    <header class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="m-0 flex flex-wrap items-center gap-2 text-xl font-semibold tracking-tight">
          {{ info.label }} {{ slip.name }}
          <StatusBadge :value="slip.state" />
          <span v-if="slip.requires_leader" class="badge badge-muted">Cần lãnh đạo duyệt</span>
          <span v-if="overdueDays" class="badge badge-danger">Quá hạn {{ overdueDays }} ngày</span>
        </h1>
        <p class="mt-1 text-sm text-ink-muted">Độc giả {{ slip.reader.full_name || slip.reader.name }} · gửi lúc {{ formatDateTime(slip.submitted_on) || "chưa gửi" }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <template v-for="[kindName, urls] in printLinks" :key="kindName">
          <a class="btn" :href="urls.view" target="_blank" rel="noopener"><Icon name="printer" :size="16" /> In {{ printLabel(kindName).toLowerCase() }}</a>
          <a class="btn" :href="urls.pdf" target="_blank" rel="noopener" :aria-label="`Tải PDF ${printLabel(kindName).toLowerCase()}`"><Icon name="download" :size="16" /> PDF</a>
        </template>
      </div>
    </header>

    <p v-if="slip.state === 'Từ chối' && slip.rejection_reason" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger"><strong>Lý do từ chối:</strong> {{ slip.rejection_reason }}</p>
    <p v-if="overdueDays" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">Tài liệu đã quá hạn trả {{ overdueDays }} ngày (hạn trả {{ formatDate(slip.due_date) }}). Độc giả chưa thể lập phiếu sử dụng mới.</p>

    <!-- what can be done next -->
    <section v-if="slip.actions.length || slip.can.renew || slip.can.delete_draft" class="card mb-5 flex flex-wrap items-center gap-2 p-4" aria-label="Thao tác">
      <button v-for="action in slip.actions" :key="action" class="btn" :class="actionStyle(action)" type="button" :disabled="busy" @click="run(action)">{{ action }}</button>
      <button v-if="slip.can.renew" class="btn" type="button" :disabled="busy" @click="Object.assign(dialog, { type: 'renew', error: '' })">
        <Icon name="calendar-plus" :size="16" /> Gia hạn
      </button>
      <button v-if="slip.can.delete_draft" class="btn btn-danger" type="button" :disabled="busy" @click="Object.assign(dialog, { type: 'delete', error: '' })">
        <Icon name="trash-2" :size="16" /> Xóa nháp
      </button>
      <span v-if="slip.renew_reason && slip.state === 'Đang sử dụng'" class="text-sm text-ink-muted">{{ slip.renew_reason }}</span>
    </section>

    <div class="mb-5 grid gap-4 lg:grid-cols-3">
      <section class="card p-4">
        <h2 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Độc giả</h2>
        <p class="m-0 font-medium">{{ slip.reader.full_name || slip.reader.name }}</p>
        <p class="m-0 text-sm text-ink-soft">{{ [slip.reader.organization, slip.reader.position].filter(Boolean).join(" — ") }}</p>
        <p class="m-0 mt-1 text-sm text-ink-muted">{{ [slip.reader.email, slip.reader.phone].filter(Boolean).join(" · ") }}</p>
        <p v-if="slip.reader.reader_group" class="m-0 mt-1 text-sm text-ink-muted">Nhóm: {{ slip.reader.reader_group }}</p>
      </section>
      <section class="card p-4">
        <h2 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">{{ info.purposeLabel }}</h2>
        <p class="m-0 whitespace-pre-line text-sm">{{ slip.purpose || "—" }}</p>
        <p v-if="slip.notes" class="m-0 mt-2 whitespace-pre-line text-sm text-ink-muted">Ghi chú: {{ slip.notes }}</p>
      </section>
      <section class="card p-4">
        <h2 class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Tiến trình</h2>
        <dl class="m-0 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-sm">
          <dt class="text-ink-muted">Ngày lập</dt><dd class="m-0">{{ formatDate(slip.request_date) }}</dd>
          <template v-if="slip.approved_by"><dt class="text-ink-muted">Duyệt bởi</dt><dd class="m-0">{{ slip.approved_by }} · {{ formatDateTime(slip.approved_date) }}</dd></template>
          <template v-if="slip.leader"><dt class="text-ink-muted">Lãnh đạo</dt><dd class="m-0">{{ slip.leader }}</dd></template>
          <template v-if="slip.issued_on"><dt class="text-ink-muted">Đã giao</dt><dd class="m-0">{{ formatDateTime(slip.issued_on) }} · {{ slip.issued_by }}</dd></template>
          <template v-if="slip.due_date"><dt class="text-ink-muted">Hạn trả</dt><dd class="m-0 font-medium">{{ formatDate(slip.due_date) }}<span v-if="slip.renewal_count"> · gia hạn {{ slip.renewal_count }}/{{ slip.max_renewals || "∞" }} lần</span></dd></template>
          <template v-if="slip.returned_date"><dt class="text-ink-muted">Đã trả</dt><dd class="m-0">{{ formatDateTime(slip.returned_date) }} · {{ slip.received_by }}</dd></template>
          <template v-if="slip.completed_date"><dt class="text-ink-muted">Hoàn thành</dt><dd class="m-0">{{ formatDateTime(slip.completed_date) }}</dd></template>
        </dl>
      </section>
    </div>

    <section class="card mb-5 overflow-hidden" aria-label="Hồ sơ, văn bản trong phiếu">
      <header class="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 class="m-0 text-base font-semibold">Hồ sơ, văn bản trong phiếu <span class="badge badge-muted">{{ items.length }}</span></h2>
        <div v-if="canDecide" class="flex items-center gap-2">
          <span class="text-sm text-ink-muted">{{ reviewLabel }} — {{ approvedCount(items) }} dòng sẽ được duyệt</span>
          <button class="btn btn-sm btn-primary" type="button" :disabled="busy || !dirty" @click="saveDecisions"><Icon name="save" :size="14" /> Lưu quyết định</button>
        </div>
      </header>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Loại</th><th scope="col">Tài liệu</th><th scope="col">Mức mật</th><th scope="col">Vị trí lưu trữ</th>
              <th v-if="kind === 'copy'" scope="col">Số bản</th><th scope="col">Kết quả</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.row">
              <td class="whitespace-nowrap">{{ item.kind }}</td>
              <td>
                <div class="font-medium">{{ item.title }}</div>
                <div class="text-xs text-ink-muted">{{ [item.number, item.parent_title && `Hồ sơ: ${item.parent_title}`].filter(Boolean).join(" · ") }}</div>
                <div v-if="item.notes" class="text-xs text-ink-muted">Ghi chú của độc giả: {{ item.notes }}</div>
              </td>
              <td><span v-if="item.level" class="badge badge-muted">{{ item.level }}</span></td>
              <td class="text-sm text-ink-soft">{{ item.location || "—" }}</td>
              <td v-if="kind === 'copy'">{{ item.copy_count }}</td>
              <td class="min-w-[220px]">
                <div v-if="canDecide" class="space-y-1">
                  <div class="inline-flex gap-1" role="group" :aria-label="`Quyết định cho ${item.title}`">
                    <button class="btn btn-sm" :class="{ 'btn-primary': item.item_status === 'Đã duyệt' }" type="button" :aria-pressed="item.item_status === 'Đã duyệt'" @click="setDecision(item, 'Đã duyệt')">Duyệt</button>
                    <button class="btn btn-sm" :class="{ 'btn-danger': item.item_status === 'Từ chối' }" type="button" :aria-pressed="item.item_status === 'Từ chối'" @click="setDecision(item, 'Từ chối')">Từ chối</button>
                  </div>
                  <input v-if="item.item_status === 'Từ chối'" v-model="item.decision_note" class="input" placeholder="Lý do từ chối (bắt buộc)" :aria-label="`Lý do từ chối ${item.title}`" />
                  <StatusBadge v-if="item.item_status === 'Chờ duyệt'" value="Chờ duyệt" />
                </div>
                <div v-else>
                  <StatusBadge :value="item.item_status" />
                  <div v-if="item.decision_note" class="mt-1 text-xs text-ink-muted">{{ item.decision_note }}</div>
                  <div v-if="item.return_condition" class="mt-1 text-xs text-ink-muted">Khi trả: {{ item.return_condition }}</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="slip.timeline.length" class="card mb-8 p-4" aria-label="Lịch sử xử lý">
      <h2 class="mb-3 text-base font-semibold">Lịch sử xử lý</h2>
      <ol class="m-0 list-none space-y-2 p-0 text-sm">
        <li v-for="(entry, index) in slip.timeline" :key="index" class="flex flex-wrap gap-x-3">
          <span class="w-36 shrink-0 text-ink-muted">{{ formatDateTime(entry.when) }}</span>
          <span class="font-medium">{{ entry.text }}</span>
          <span class="text-ink-muted">· {{ entry.who }}</span>
        </li>
      </ol>
    </section>

    <!-- dialogs -->
    <ReasonDialog
      :open="dialog.type === 'reason'" :title="`${dialog.action}`" label="Lý do từ chối" :confirm-text="dialog.action" danger :busy="busy" :error="dialog.error"
      :message="`${info.label} ${slip.name} sẽ bị từ chối. Độc giả nhận được lý do này.`"
      @confirm="(text) => perform(dialog.action, text)" @cancel="closeDialog"
    />
    <ConfirmDialog
      :open="dialog.type === 'confirm'" :title="dialog.action" :message="dialog.action ? confirmText(dialog.action, slip) : ''" :confirm-text="dialog.action"
      :danger="dialog.action === 'Hủy phiếu'" :busy="busy" :error="dialog.error" @confirm="perform(dialog.action)" @cancel="closeDialog"
    />
    <ConfirmDialog
      :open="dialog.type === 'renew'" title="Gia hạn tài liệu" :busy="busy" :error="dialog.error" confirm-text="Gia hạn"
      :message="`Gia hạn thêm ${slip.renewal_days} ngày cho ${slip.reader.full_name || slip.reader.name}? Đã gia hạn ${slip.renewal_count}/${slip.max_renewals || '∞'} lần.`"
      @confirm="renew" @cancel="closeDialog"
    />
    <ConfirmDialog
      :open="dialog.type === 'delete'" danger title="Xóa phiếu nháp" :message="`Xóa phiếu nháp ${slip.name}? Thao tác này không thể hoàn tác.`" confirm-text="Xóa"
      :busy="busy" :error="dialog.error" @confirm="removeDraft" @cancel="closeDialog"
    />

    <Teleport to="body">
      <div v-if="dialog.type === 'return'" class="fixed inset-0 z-[60] grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="Nhận trả tài liệu">
        <div class="absolute inset-0 bg-black/45" @click="closeDialog"></div>
        <section class="card relative w-full max-w-lg p-5 shadow-pop">
          <h2 class="m-0 text-base font-semibold">Nhận trả tài liệu</h2>
          <p class="mt-2 text-sm text-ink-soft">Kiểm tra tình trạng từng hồ sơ, văn bản độc giả trả lại rồi xác nhận.</p>
          <ul class="mt-3 max-h-72 list-none space-y-2 overflow-y-auto p-0">
            <li v-for="item in items.filter((i) => i.item_status === 'Đã giao')" :key="item.row" class="flex items-center justify-between gap-3">
              <span class="min-w-0 truncate text-sm">{{ item.title }}</span>
              <select v-model="dialog.conditions[item.row]" class="input w-40" :aria-label="`Tình trạng của ${item.title}`">
                <option v-for="condition in CONDITIONS" :key="condition" :value="condition">{{ condition }}</option>
              </select>
            </li>
          </ul>
          <p v-if="dialog.error" class="mt-3 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ dialog.error }}</p>
          <div class="mt-5 flex justify-end gap-2">
            <button class="btn" type="button" :disabled="busy" @click="closeDialog">Hủy</button>
            <button class="btn btn-primary" type="button" :disabled="busy" @click="receiveReturn"><Icon v-if="busy" name="loader" :size="16" spin /> Xác nhận đã nhận trả</button>
          </div>
        </section>
      </div>
    </Teleport>
  </template>
</template>
