<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import LinkSelect from "../components/LinkSelect.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import PreserveJobDrawer from "../components/PreserveJobDrawer.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { formatDateTime } from "../lib/format.js";
import { ageText, ageTone, BACKUP_TYPES, CHECK_TYPES, formatBytes, jobResult, jobType, KINDS, parseNames, STATUS_FILTERS } from "../lib/preservation.js";
import { toast } from "../lib/toast.js";
import { useRoute, useRouter } from "vue-router";

// The jobs of one kind (backups, integrity checks, restores): the overview, the list, a form to start one, and the detail drawer.
const props = defineProps({ kind: { type: String, required: true } });
const route = useRoute();
const router = useRouter();

const meta = computed(() => KINDS[props.kind]);
const list = ref({ data: [], total: 0, page: 1, page_size: 20 });
const overview = ref(null);
const status = ref("");
const loading = ref(false);
const error = ref("");
const opened = ref(String(route.query.open || ""));
const openedKind = ref(props.kind);
const creating = ref(false);
const form = ref({ type: "", fonds: "", notes: "", names: "" });
const saving = ref(false);
const formError = ref("");
const retention = ref(false);
let timer = null;
let ticket = 0;

const busyRows = computed(() => list.value.data.some((j) => j.busy));
const site = computed(() => overview.value?.site || "");

async function loadOverview() {
  try {
    overview.value = await api.preservation.overview();
  } catch (e) {
    error.value = e.message;
  }
}

async function load(page = list.value.page, quiet = false) {
  const mine = ++ticket; // the answer of a request for a kind the user has left must not overwrite the list
  const kind = props.kind;
  if (!quiet) loading.value = true;
  try {
    const answer = await api.preservation.jobs(kind, { status: status.value || undefined, page });
    if (mine !== ticket) return;
    list.value = answer;
    error.value = "";
  } catch (e) {
    if (mine === ticket) error.value = e.message;
  } finally {
    if (mine === ticket) loading.value = false;
  }
  if (mine === ticket) schedule();
}
function schedule() {
  clearTimeout(timer);
  if (busyRows.value) timer = setTimeout(() => load(list.value.page, true), 3000);
}
watch(() => props.kind, () => {
  clearTimeout(timer);
  status.value = "";
  list.value = { data: [], total: 0, page: 1, page_size: 20 };
  opened.value = String(route.query.open || "");
  openedKind.value = props.kind;
  load(1);
  loadOverview();
}, { immediate: true });
watch(status, () => load(1));
onBeforeUnmount(() => clearTimeout(timer));

function onChanged() {
  load(list.value.page, true);
  if (props.kind === "backup") loadOverview();
}

function openJob(name, kind = props.kind) {
  if (kind !== props.kind) {
    router.push({ path: KINDS[kind].route, query: { open: name } });
    return;
  }
  openedKind.value = kind;
  opened.value = name;
  router.replace({ query: name ? { open: name } : {} });
}
watch(() => route.query.open, (name) => { if (name && name !== opened.value) { openedKind.value = props.kind; opened.value = String(name); } });

function startForm() {
  form.value = { type: props.kind === "backup" ? "Cả hai" : props.kind === "integrity" ? "Toàn bộ" : "", fonds: "", notes: "", names: "" };
  formError.value = "";
  creating.value = true;
}
async function submit() {
  saving.value = true;
  formError.value = "";
  try {
    let job;
    if (props.kind === "backup") job = await api.preservation.startBackup(form.value.type, form.value.fonds || null, form.value.notes);
    else if (props.kind === "integrity") job = await api.preservation.startCheck(form.value.type, form.value.fonds || null);
    else job = await api.preservation.startRestore({ documents: parseNames(form.value.names) });
    creating.value = false;
    toast("Đã bắt đầu");
    openJob(job.name);
    load(1);
    loadOverview();
  } catch (e) {
    formError.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function cleanUp() {
  try {
    const result = await api.preservation.runRetention();
    toast(result.removed.length ? `Đã xóa ${result.removed.length} đợt sao lưu cũ` : "Không có đợt sao lưu nào quá hạn");
    retention.value = false;
    load(1);
    loadOverview();
  } catch (e) {
    error.value = e.message;
    retention.value = false;
  }
}
const last = computed(() => overview.value?.last_backup);
const settings = computed(() => overview.value?.settings);
</script>

<template>
  <PageHeader :title="meta.title" :subtitle="meta.subtitle">
    <button v-if="kind === 'backup'" class="btn" type="button" @click="retention = true"><Icon name="trash-2" :size="16" /> Dọn bản cũ</button>
    <button class="btn btn-primary" type="button" @click="startForm"><Icon name="plus" :size="16" /> {{ meta.create }}</button>
  </PageHeader>

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

  <section v-if="kind === 'backup' && overview" class="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Tình hình sao lưu">
    <div class="card px-4 py-3">
      <p class="m-0 text-xs uppercase text-ink-muted">Bản sao lưu gần nhất</p>
      <p class="m-0 text-lg font-semibold"><span :class="`text-${ageTone(last?.age_days, settings?.backup_frequency)}`">{{ ageText(last?.age_days) }}</span></p>
      <p class="m-0 text-xs text-ink-muted">{{ last ? `${last.name} · ${last.backup_type}` : "Chưa có bản sao lưu nào" }}</p>
    </div>
    <div class="card px-4 py-3">
      <p class="m-0 text-xs uppercase text-ink-muted">Sao lưu theo lịch</p>
      <p class="m-0 text-lg font-semibold">{{ settings?.auto_backup_enabled ? settings.backup_frequency : "Đang tắt" }}</p>
      <p class="m-0 text-xs text-ink-muted">Giữ {{ settings?.backup_retention_days }} ngày · <RouterLink to="/quan-tri/thiet-lap-he-thong">đổi ở thiết lập</RouterLink></p>
    </div>
    <div class="card px-4 py-3">
      <p class="m-0 text-xs uppercase text-ink-muted">Kho tệp sao lưu</p>
      <p class="m-0 text-lg font-semibold">{{ formatBytes(overview.store.bytes) }}</p>
      <p class="m-0 text-xs text-ink-muted">{{ overview.store.blobs }} tệp · {{ overview.store.manifests }} bảng kê</p>
    </div>
    <div class="card px-4 py-3">
      <p class="m-0 text-xs uppercase text-ink-muted">Dung lượng đĩa còn trống</p>
      <p class="m-0 text-lg font-semibold">{{ overview.disk ? `${overview.disk.free_gb} GB` : "—" }}</p>
      <p class="m-0 text-xs text-ink-muted">{{ overview.disk ? `trên ${overview.disk.total_gb} GB` : "" }}</p>
    </div>
  </section>

  <section class="card">
    <header class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
      <label class="flex items-center gap-2 text-sm">Trạng thái
        <select v-model="status" class="input w-auto"><option v-for="s in STATUS_FILTERS" :key="s" :value="s">{{ s || "Tất cả" }}</option></select>
      </label>
      <span class="ml-auto text-xs text-ink-muted" aria-live="polite">{{ busyRows ? "Đang cập nhật tiến độ…" : "" }}</span>
    </header>
    <div v-if="loading && !list.data.length" class="space-y-2 p-5"><div v-for="n in 4" :key="n" class="h-9 animate-pulse rounded bg-surface-muted"></div></div>
    <EmptyState v-else-if="!list.data.length" :icon="meta.icon" title="Chưa có đợt nào" text="Bấm nút tạo ở góc trên để bắt đầu." />
    <div v-else class="table-wrap" :class="{ 'opacity-60': loading }">
      <table class="data-table">
        <caption class="sr-only">{{ meta.title }}</caption>
        <thead><tr><th scope="col">Mã</th><th scope="col">Loại</th><th scope="col">Trạng thái</th><th scope="col">Kết quả</th><th scope="col">Bắt đầu</th><th scope="col">Người thực hiện</th></tr></thead>
        <tbody>
          <tr v-for="job in list.data" :key="job.name" class="is-clickable" tabindex="0" @click="openJob(job.name)" @keydown.enter="openJob(job.name)">
            <td class="whitespace-nowrap font-medium">{{ job.name }}</td>
            <td>{{ jobType(kind, job) }}<span v-if="job.trigger === 'Theo lịch'" class="badge badge-muted ml-1">lịch</span></td>
            <td class="whitespace-nowrap"><StatusBadge :value="job.status" /><span v-if="job.busy" class="ml-2 text-xs text-ink-muted">{{ job.percent }}%</span></td>
            <td class="text-sm text-ink-soft">{{ jobResult(kind, job) }}</td>
            <td class="whitespace-nowrap text-sm text-ink-muted">{{ formatDateTime(job.started_at || job.creation) }}</td>
            <td class="text-sm text-ink-muted">{{ job.initiated_by || (job.trigger === "Theo lịch" ? "Hệ thống" : "") }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginationBar v-if="list.total" :page="list.page" :page-size="list.page_size" :total="list.total" @change="load" />
  </section>

  <PreserveJobDrawer :kind="openedKind" :name="opened" :site="site" @close="openJob('')" @changed="onChanged" @open="(target) => openJob(target.name, target.kind)" />

  <Drawer :open="creating" :title="meta.create" width="520px" @close="creating = false">
    <form class="space-y-4" @submit.prevent="submit">
      <p v-if="formError" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ formError }}</p>
      <template v-if="kind === 'backup'">
        <label class="block text-sm"><span class="label">Sao lưu gì</span>
          <select v-model="form.type" class="input"><option v-for="[value, label] in BACKUP_TYPES" :key="value" :value="value">{{ label }}</option></select></label>
        <div v-if="form.type !== 'Cơ sở dữ liệu'"><span class="label">Phạm vi tệp (phông)</span><LinkSelect v-model="form.fonds" doctype="Fonds" placeholder="Tất cả các phông" /></div>
        <label class="block text-sm"><span class="label">Ghi chú</span><textarea v-model="form.notes" class="input" rows="2"></textarea></label>
        <p class="m-0 text-xs text-ink-muted">Việc sao lưu chạy nền; chỉ các tệp mới hoặc đã thay đổi được chép thêm vào kho, các tệp đã có không chép lại.</p>
      </template>
      <template v-else-if="kind === 'integrity'">
        <label class="block text-sm"><span class="label">Loại kiểm tra</span>
          <select v-model="form.type" class="input"><option v-for="[value, label] in CHECK_TYPES" :key="value" :value="value">{{ label }}</option></select></label>
        <div><span class="label">Phạm vi (phông)</span><LinkSelect v-model="form.fonds" doctype="Fonds" placeholder="Tất cả các phông" /></div>
      </template>
      <template v-else>
        <label class="block text-sm"><span class="label">Mã các văn bản cần khôi phục tệp (mỗi dòng một mã)</span>
          <textarea v-model="form.names" class="input" rows="6" placeholder="DOC-000123&#10;DOC-000124"></textarea></label>
        <p class="m-0 text-xs text-ink-muted">Tệp được lấy từ bản sao lưu mới nhất có chứa tài liệu. Để khôi phục theo kết quả kiểm tra, mở đợt kiểm tra rồi bấm “Chuyển sang khôi phục”; khôi phục cơ sở dữ liệu bắt đầu từ một đợt sao lưu.</p>
      </template>
    </form>
    <template #footer>
      <button class="btn" type="button" @click="creating = false">Hủy</button>
      <button class="btn btn-primary" type="button" :disabled="saving || (kind === 'restore' && !parseNames(form.names).length)" @click="submit">
        <Icon :name="saving ? 'loader' : 'play'" :size="16" :spin="saving" /> Bắt đầu
      </button>
    </template>
  </Drawer>

  <ConfirmDialog :open="retention" danger title="Dọn các bản sao lưu cũ?" confirm-text="Dọn" message="Các đợt sao lưu quá thời hạn lưu sẽ bị xóa cùng các tệp chỉ chúng dùng. Hệ thống luôn giữ lại số đợt thành công mới nhất theo thiết lập." @confirm="cleanUp" @cancel="retention = false" />
</template>
