<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { formatDateTime, formatNumber } from "../lib/format.js";
import { codeLabel, confirmMatches, downloadBackupUrl, formatMb, isCounterCode, jobType, KINDS, parseNames } from "../lib/preservation.js";
import { toast } from "../lib/toast.js";
import ConfirmDialog from "./ConfirmDialog.vue";
import Drawer from "./Drawer.vue";
import Icon from "./Icon.vue";
import PaginationBar from "./PaginationBar.vue";
import StatusBadge from "./StatusBadge.vue";

// One backup, integrity check or restore batch: its progress while it runs, what it produced and the actions that fit its state.
const props = defineProps({ kind: { type: String, required: true }, name: { type: String, default: "" }, site: { type: String, default: "" } });
const emit = defineEmits(["close", "changed", "open"]);

const job = ref(null);
const error = ref("");
const busy = ref("");
const confirm = ref("");
const findings = ref({ data: [], total: 0, page: 1, page_size: 50 });
const severity = ref("");
const findingStatus = ref("");
const verification = ref(null);
const names = ref("");
const prepared = ref(null);
const typedSite = ref("");
let timer = null;

const open = computed(() => Boolean(props.name));
const meta = computed(() => KINDS[props.kind]);
const hasCounters = computed(() => findings.value.data.some((f) => isCounterCode(f.code)));

async function load(quiet = false) {
  if (!props.name) return;
  try {
    job.value = await api.preservation.job(props.kind, props.name);
    error.value = "";
    if (props.kind === "integrity") await loadFindings(findings.value.page);
  } catch (e) {
    if (!quiet) error.value = e.message;
  }
  schedule();
}
function schedule() {
  clearTimeout(timer);
  if (job.value?.busy && props.name) timer = setTimeout(() => load(true).then(() => emit("changed")), 2500);
}
async function loadFindings(page = 1) {
  findings.value = await api.preservation.findings(props.name, { page, severity: severity.value || undefined, status: findingStatus.value || undefined });
}
watch(() => props.name, (name) => {
  job.value = null;
  error.value = "";
  verification.value = null;
  prepared.value = null;
  names.value = "";
  typedSite.value = "";
  if (name) load();
}, { immediate: true });
watch([severity, findingStatus], () => props.kind === "integrity" && loadFindings(1));
onBeforeUnmount(() => clearTimeout(timer));

async function act(label, fn, message) {
  busy.value = label;
  error.value = "";
  try {
    const result = await fn();
    if (message) toast(message);
    return result;
  } catch (e) {
    error.value = e.message;
    return null;
  } finally {
    busy.value = "";
    confirm.value = "";
  }
}
async function refresh() {
  await load();
  emit("changed");
}
const cancel = () => act("cancel", () => api.preservation.cancel(props.kind, props.name), "Đã yêu cầu dừng").then(refresh);
const resume = () => act("resume", () => api.preservation.resume(props.kind, props.name), "Đã chạy tiếp").then(refresh);
async function remove() {
  const done = await act("remove", () => api.preservation.remove(props.kind, props.name), "Đã xóa");
  if (done) {
    emit("changed");
    emit("close");
  }
}
const verify = () => act("verify", () => api.preservation.verifyBackup(props.name)).then((r) => { if (r) verification.value = r; });
async function restoreFiles() {
  const created = await act("restore", () => api.preservation.startRestore({ documents: parseNames(names.value), source_backup: props.name }), "Đã tạo đợt phục hồi");
  if (created) {
    emit("changed");
    emit("open", { kind: "restore", name: created.name });
  }
}
async function restoreFromCheck() {
  const created = await act("restore", () => api.preservation.startRestore({ check: props.name }), "Đã tạo đợt phục hồi từ các lỗi");
  if (created) {
    emit("changed");
    emit("open", { kind: "restore", name: created.name });
  }
}
const fix = () => act("fix", () => api.preservation.fixCounters(), "Đã sửa bộ đếm").then((r) => r && toast(`${r.fonds} phông, ${r.files} hồ sơ`));
const setFinding = (finding, status) => act("finding", () => api.preservation.setFinding(finding.name, status)).then(() => loadFindings(findings.value.page));
async function prepare() {
  const result = await act("prepare", () => api.preservation.prepareDbRestore(props.name));
  if (result) {
    prepared.value = result;
    if (result.batch) emit("changed");
  }
}
const runDb = () => act("rundb", () => api.preservation.runRestore(prepared.value.batch.name, typedSite.value), "Đã gửi yêu cầu khôi phục").then(() => emit("open", { kind: "restore", name: prepared.value.batch.name }));
const runRestore = () => act("run", () => api.preservation.runRestore(props.name, typedSite.value), "Đã gửi yêu cầu").then(refresh);
</script>

<template>
  <Drawer :open="open" :title="job ? `${meta.title}: ${job.name}` : meta.title" width="860px" @close="emit('close')">
    <p v-if="error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
    <div v-if="!job" class="flex items-center gap-2 py-8 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>

    <div v-else class="space-y-6">
      <section class="space-y-3">
        <div class="flex flex-wrap items-center gap-3">
          <StatusBadge :value="job.status" />
          <span class="text-sm text-ink-soft">{{ jobType(kind, job) }}<template v-if="job.fonds"> · phông {{ job.fonds }}</template></span>
          <span v-if="job.trigger" class="badge badge-muted">{{ job.trigger }}</span>
          <span v-if="job.phase" class="badge badge-info">{{ job.phase }}</span>
        </div>
        <div v-if="job.busy || job.percent < 100" class="space-y-1" aria-live="polite">
          <div class="h-2 overflow-hidden rounded-full bg-surface-muted" role="progressbar" :aria-valuenow="job.percent" aria-valuemin="0" aria-valuemax="100">
            <div class="h-2 rounded-full bg-primary transition-all" :style="{ width: `${job.percent}%` }"></div>
          </div>
          <p class="m-0 text-xs text-ink-muted">{{ job.percent }}%</p>
        </div>
        <p class="m-0 text-sm text-ink-muted">Bắt đầu {{ formatDateTime(job.started_at) || "—" }} · kết thúc {{ formatDateTime(job.completed_at) || "—" }}<template v-if="job.initiated_by"> · bởi {{ job.initiated_by }}</template></p>
        <div class="flex flex-wrap gap-2">
          <button v-if="job.can_cancel" class="btn" type="button" :disabled="Boolean(busy)" @click="cancel"><Icon name="ban" :size="16" /> Dừng</button>
          <button v-if="job.can_resume" class="btn" type="button" :disabled="Boolean(busy)" @click="resume"><Icon name="play" :size="16" /> Chạy tiếp</button>
          <button v-if="kind === 'restore' && job.restore_type === 'Cơ sở dữ liệu' && !job.busy" class="btn" type="button" :disabled="Boolean(busy)" @click="confirm = 'runDb'"><Icon name="play" :size="16" /> Chạy khôi phục</button>
          <button v-if="job.can_delete" class="btn text-danger" type="button" :disabled="Boolean(busy)" @click="confirm = 'remove'"><Icon name="trash-2" :size="16" /> Xóa</button>
        </div>
      </section>

      <!-- backup -->
      <template v-if="kind === 'backup'">
        <section v-if="job.database.file || job.backup_type !== 'Tệp tài liệu'" class="card px-4 py-3">
          <h3 class="mb-2 mt-0 text-sm font-semibold">Cơ sở dữ liệu</h3>
          <p v-if="!job.database.file" class="m-0 text-sm text-ink-muted">Chưa có tệp sao lưu cơ sở dữ liệu.</p>
          <dl v-else class="m-0 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            <div><dt class="inline text-ink-muted">Tệp: </dt><dd class="inline font-medium">{{ job.database.file }}</dd></div>
            <div><dt class="inline text-ink-muted">Dung lượng: </dt><dd class="inline font-medium">{{ formatMb(job.database.size_mb) }}</dd></div>
            <div class="sm:col-span-2"><dt class="inline text-ink-muted">SHA-256: </dt><dd class="inline break-all font-mono text-xs">{{ job.database.checksum }}</dd></div>
          </dl>
          <div v-if="job.database.file" class="mt-3 flex flex-wrap gap-2">
            <button class="btn" type="button" :disabled="Boolean(busy)" @click="verify"><Icon name="shield-check" :size="16" /> Kiểm tra bản sao lưu</button>
            <a v-if="job.has_database" class="btn" :href="downloadBackupUrl(job.name)"><Icon name="download" :size="16" /> Tải về</a>
            <button class="btn" type="button" :disabled="Boolean(busy)" @click="prepare"><Icon name="undo" :size="16" /> Khôi phục từ bản này…</button>
          </div>
          <p v-if="verification" class="mb-0 mt-3 rounded-md px-3 py-2 text-sm" :class="verification.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'" role="status">
            <template v-if="verification.ok">Bản sao lưu hợp lệ: đọc được và đúng mã SHA-256 ghi lúc sao lưu.</template>
            <template v-else>{{ verification.problems.join(" ") }}</template>
          </p>
          <div v-if="prepared" class="mt-3 space-y-2 border-t border-line pt-3">
            <p v-if="!prepared.batch" class="m-0 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">{{ prepared.verification.problems.join(" ") }}</p>
            <template v-else>
              <p class="m-0 text-sm">Đã tạo đợt phục hồi <button class="font-semibold text-primary hover:underline" type="button" @click="emit('open', { kind: 'restore', name: prepared.batch.name })">{{ prepared.batch.name }}</button>. Hệ thống chưa thay đổi gì.</p>
              <pre class="m-0 max-h-60 overflow-auto whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-xs">{{ prepared.runbook }}</pre>
              <div v-if="prepared.can_run" class="flex flex-wrap items-end gap-2">
                <label class="min-w-[16rem] flex-1 text-sm"><span class="label">Gõ tên site <strong>{{ prepared.site }}</strong> để cho phép hệ thống tự khôi phục</span><input v-model="typedSite" class="input" type="text" autocomplete="off" /></label>
                <button class="btn btn-danger" type="button" :disabled="!confirmMatches(typedSite, prepared.site) || Boolean(busy)" @click="runDb"><Icon name="play" :size="16" /> Chạy khôi phục</button>
              </div>
              <p v-else class="m-0 text-xs text-ink-muted">Tự khôi phục đang tắt: làm theo các lệnh trên trên máy chủ.</p>
            </template>
          </div>
        </section>

        <section v-if="job.backup_type !== 'Cơ sở dữ liệu'" class="card px-4 py-3">
          <h3 class="mb-2 mt-0 text-sm font-semibold">Tệp tài liệu</h3>
          <p class="m-0 text-sm">{{ formatNumber(job.files.done) }} / {{ formatNumber(job.files.total) }} tệp · {{ formatMb(job.files.size_mb) }}<template v-if="job.files.failed"> · <span class="font-semibold text-danger">{{ job.files.failed }} lỗi</span></template></p>
          <div class="mt-3 flex flex-wrap gap-2">
            <a v-if="job.has_files" class="btn" :href="downloadBackupUrl(job.name, 'manifest')"><Icon name="file-down" :size="16" /> Tải bảng kê (manifest)</a>
          </div>
          <div v-if="job.has_files" class="mt-3 space-y-2 border-t border-line pt-3">
            <label class="text-sm"><span class="label">Phục hồi tệp của các văn bản từ bản này (mã văn bản, mỗi dòng một mã)</span><textarea v-model="names" class="input" rows="3" placeholder="DOC-000123&#10;DOC-000124"></textarea></label>
            <button class="btn" type="button" :disabled="!parseNames(names).length || Boolean(busy)" @click="restoreFiles"><Icon name="undo" :size="16" /> Tạo đợt phục hồi ({{ parseNames(names).length }})</button>
          </div>
        </section>
        <p v-if="job.expires_on" class="m-0 text-xs text-ink-muted">Được giữ đến {{ job.expires_on }} theo thời hạn lưu bản sao lưu.</p>
      </template>

      <!-- integrity -->
      <template v-if="kind === 'integrity'">
        <section class="grid gap-3 sm:grid-cols-3">
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Tài liệu đã kiểm tra</p><p class="m-0 text-xl font-semibold">{{ formatNumber(job.total_checked) }}</p></div>
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Lỗi</p><p class="m-0 text-xl font-semibold" :class="job.errors ? 'text-danger' : ''">{{ formatNumber(job.errors) }}</p></div>
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Cảnh báo</p><p class="m-0 text-xl font-semibold" :class="job.warnings ? 'text-warning' : ''">{{ formatNumber(job.warnings) }}</p></div>
        </section>
        <p v-if="job.summary" class="m-0 text-sm text-ink-soft">{{ job.summary }}</p>
        <div class="flex flex-wrap gap-2">
          <button v-if="job.restorable" class="btn btn-primary" type="button" :disabled="Boolean(busy)" @click="restoreFromCheck"><Icon name="undo" :size="16" /> Chuyển sang khôi phục ({{ job.restorable }} tài liệu có thể phục hồi)</button>
          <button v-if="hasCounters" class="btn" type="button" :disabled="Boolean(busy)" @click="fix"><Icon name="refresh-cw" :size="16" /> Sửa bộ đếm</button>
        </div>
        <section class="card">
          <header class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
            <h3 class="m-0 mr-auto text-sm font-semibold">Phát hiện ({{ formatNumber(findings.total) }})</h3>
            <select v-model="severity" class="input w-auto" aria-label="Lọc theo mức độ"><option value="">Mọi mức độ</option><option>Lỗi</option><option>Cảnh báo</option></select>
            <select v-model="findingStatus" class="input w-auto" aria-label="Lọc theo xử lý"><option value="">Mọi trạng thái</option><option>Chưa xử lý</option><option>Đã khôi phục</option><option>Đã bỏ qua</option></select>
          </header>
          <p v-if="!findings.data.length" class="m-0 px-4 py-6 text-center text-sm text-ink-muted">Không có phát hiện nào.</p>
          <div v-else class="table-wrap">
            <table class="data-table">
              <caption class="sr-only">Các phát hiện của đợt kiểm tra</caption>
              <thead><tr><th scope="col">Mức</th><th scope="col">Loại</th><th scope="col">Văn bản</th><th scope="col">Nội dung</th><th scope="col">Xử lý</th><th scope="col"><span class="sr-only">Thao tác</span></th></tr></thead>
              <tbody>
                <tr v-for="f in findings.data" :key="f.name">
                  <td><StatusBadge :value="f.severity" /></td>
                  <td class="whitespace-nowrap text-sm">{{ codeLabel(f.code) }}</td>
                  <td class="whitespace-nowrap text-sm"><RouterLink v-if="f.document" :to="`/van-ban/${encodeURIComponent(f.document)}`">{{ f.document }}</RouterLink></td>
                  <td class="break-words text-sm">{{ f.message }}<span v-if="f.restorable" class="badge badge-success ml-2">Phục hồi được</span></td>
                  <td><StatusBadge :value="f.status" /></td>
                  <td class="text-right"><button v-if="f.status !== 'Đã khôi phục'" class="text-sm text-primary hover:underline" type="button" @click="setFinding(f, f.status === 'Đã bỏ qua' ? 'Chưa xử lý' : 'Đã bỏ qua')">{{ f.status === "Đã bỏ qua" ? "Mở lại" : "Bỏ qua" }}</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <PaginationBar v-if="findings.total > findings.page_size" :page="findings.page" :page-size="findings.page_size" :total="findings.total" @change="loadFindings" />
        </section>
      </template>

      <!-- restore -->
      <template v-if="kind === 'restore'">
        <section class="grid gap-3 sm:grid-cols-3" v-if="job.restore_type !== 'Cơ sở dữ liệu'">
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Tài liệu</p><p class="m-0 text-xl font-semibold">{{ formatNumber(job.total) }}</p></div>
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Đã phục hồi</p><p class="m-0 text-xl font-semibold text-success">{{ formatNumber(job.restored) }}</p></div>
          <div class="card px-4 py-3"><p class="m-0 text-xs uppercase text-ink-muted">Lỗi</p><p class="m-0 text-xl font-semibold" :class="job.failed ? 'text-danger' : ''">{{ formatNumber(job.failed) }}</p></div>
        </section>
        <p v-if="job.source_backup || job.source_check" class="m-0 text-sm text-ink-soft">
          <template v-if="job.source_backup">Nguồn: <button class="font-semibold text-primary hover:underline" type="button" @click="emit('open', { kind: 'backup', name: job.source_backup })">{{ job.source_backup }}</button></template>
          <template v-if="job.source_check"> · từ đợt kiểm tra <button class="font-semibold text-primary hover:underline" type="button" @click="emit('open', { kind: 'integrity', name: job.source_check })">{{ job.source_check }}</button></template>
        </p>
        <div v-if="job.restore_type === 'Cơ sở dữ liệu' && !job.busy" class="flex flex-wrap items-end gap-2">
          <label class="min-w-[16rem] flex-1 text-sm"><span class="label">Gõ tên site <strong>{{ site }}</strong> nếu muốn hệ thống tự chạy (khi đã được cho phép)</span><input v-model="typedSite" class="input" type="text" autocomplete="off" /></label>
        </div>
        <section v-if="job.items?.length" class="card">
          <div class="table-wrap">
            <table class="data-table">
              <caption class="sr-only">Các tài liệu của đợt phục hồi</caption>
              <thead><tr><th scope="col">Văn bản</th><th scope="col">Trạng thái</th><th scope="col">Nguồn</th><th scope="col">Kết quả</th></tr></thead>
              <tbody>
                <tr v-for="item in job.items" :key="item.name">
                  <td class="whitespace-nowrap text-sm"><RouterLink :to="`/van-ban/${encodeURIComponent(item.document)}`">{{ item.document }}</RouterLink></td>
                  <td><StatusBadge :value="item.status" /></td>
                  <td class="whitespace-nowrap text-xs text-ink-muted">{{ item.source_backup }}</td>
                  <td class="break-words text-sm">{{ item.message }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="job.items_total > job.items.length" class="m-0 border-t border-line px-4 py-2 text-xs text-ink-muted">Hiện {{ job.items.length }} / {{ formatNumber(job.items_total) }} dòng.</p>
        </section>
      </template>

      <section v-if="job.log">
        <h3 class="mb-2 mt-0 text-sm font-semibold">Ghi chú, nhật ký</h3>
        <pre class="m-0 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-xs">{{ job.log }}</pre>
      </section>

      <section v-if="kind === 'backup' && job.items?.length" class="card">
        <h3 class="m-0 border-b border-line px-4 py-3 text-sm font-semibold">Tệp không sao lưu được ({{ formatNumber(job.items_total) }})</h3>
        <div class="table-wrap"><table class="data-table"><tbody>
          <tr v-for="item in job.items" :key="item.name"><td class="whitespace-nowrap text-sm"><RouterLink v-if="item.document" :to="`/van-ban/${encodeURIComponent(item.document)}`">{{ item.document }}</RouterLink></td><td class="break-words text-sm">{{ item.message }}</td></tr>
        </tbody></table></div>
      </section>
    </div>

    <ConfirmDialog :open="confirm === 'remove'" danger title="Xóa đợt này?" confirm-text="Xóa" :busy="busy === 'remove'" :error="error"
      :message="kind === 'backup' ? 'Tệp sao lưu cơ sở dữ liệu, bảng kê và các bản sao tệp không còn đợt nào dùng sẽ bị xóa khỏi máy chủ.' : 'Đợt này và các dòng chi tiết của nó sẽ bị xóa.'" @confirm="remove" @cancel="confirm = ''" />
    <ConfirmDialog :open="confirm === 'runDb'" danger title="Chạy khôi phục cơ sở dữ liệu?" confirm-text="Chạy" :busy="busy === 'run'"
      message="Hệ thống kiểm tra bản sao lưu rồi, nếu site đã cho phép và tên site đúng, sẽ thay toàn bộ dữ liệu hiện tại bằng bản sao lưu. Nếu chưa cho phép, hệ thống chỉ đưa ra các lệnh cần chạy trên máy chủ."
      @confirm="runRestore" @cancel="confirm = ''" />
  </Drawer>
</template>
