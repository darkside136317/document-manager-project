<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import Breadcrumbs from "../components/Breadcrumbs.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import DocumentPreview from "../components/DocumentPreview.vue";
import EmptyState from "../components/EmptyState.vue";
import FileUploader from "../components/FileUploader.vue";
import FormRenderer from "../components/FormRenderer.vue";
import Icon from "../components/Icon.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { blankRecord, describe, missingRequired } from "../lib/doctype.js";
import { formatDateTime } from "../lib/format.js";
import { pageTitle } from "../lib/page.js";
import { toast } from "../lib/toast.js";
import { formatSize } from "../lib/upload.js";

// One document: its file (preview, download, replace) beside its description.
const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));

const meta = ref(null);
const overview = ref(null);
const preview = ref(null);
const record = reactive({});
const original = ref("");
const loading = ref(true);
const previewLoading = ref(false);
const previewError = ref("");
const error = ref("");
const saveError = ref("");
const fieldErrors = reactive({});
const saving = ref(false);
const replaceOpen = ref(false);
const confirmDelete = reactive({ open: false, busy: false, error: "" });
let timer = null;

const dirty = computed(() => JSON.stringify(record) !== original.value);
const canWrite = computed(() => overview.value?.permissions.write);
const info = computed(() => overview.value?.file);
const printEntries = computed(() => Object.values(overview.value?.print || {}));

function assign(values) {
  for (const key of Object.keys(record)) delete record[key];
  Object.assign(record, values);
  original.value = JSON.stringify(record);
}

async function loadPreview() {
  preview.value = null;
  previewError.value = "";
  if (!info.value?.attached) return;
  previewLoading.value = true;
  try {
    preview.value = await api.preview(name.value);
  } catch (e) {
    previewError.value = e.message;
  } finally {
    previewLoading.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [doc, ov, m] = await Promise.all([api.get("Archive Document", name.value), api.archive.documentOverview(name.value), describe("Archive Document")]);
    meta.value = m;
    overview.value = ov;
    assign({ ...blankRecord(m), ...doc });
    pageTitle.value = doc.document_title || name.value;
    await loadPreview();
    schedulePoll();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

// The file is read, stored and indexed in the background: follow it until it settles.
function schedulePoll() {
  clearTimeout(timer);
  if (info.value && info.value.attached && ["Đang xử lý", "Chưa index"].includes(info.value.index_status)) {
    timer = setTimeout(async () => {
      try {
        overview.value = await api.archive.documentOverview(name.value);
      } catch {
        return;
      }
      if (info.value.index_status === "Đã index") await loadPreview();
      schedulePoll();
    }, 3000);
  }
}
onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
watch(name, load);

async function save() {
  saveError.value = "";
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  const missing = missingRequired(meta.value, record);
  for (const item of missing) fieldErrors[item.fieldname] = `Vui lòng nhập ${item.label.toLowerCase()}`;
  if (missing.length) return (saveError.value = "Còn trường bắt buộc chưa được nhập.");
  saving.value = true;
  try {
    const saved = await api.save("Archive Document", { ...record }, name.value);
    assign({ ...record, ...saved });
    pageTitle.value = saved.document_title || name.value;
    toast("Đã lưu thay đổi");
    overview.value = await api.archive.documentOverview(name.value);
  } catch (e) {
    saveError.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function afterReplace() {
  replaceOpen.value = false;
  toast("Đã cập nhật tệp của văn bản");
  overview.value = await api.archive.documentOverview(name.value);
  await loadPreview();
  schedulePoll();
}
async function reindex() {
  try {
    await api.archive.reindex(name.value);
    toast("Đã đưa vào hàng đợi xử lý lại");
    overview.value = await api.archive.documentOverview(name.value);
    schedulePoll();
  } catch (e) {
    toast(e.message, "error");
  }
}
async function remove() {
  confirmDelete.busy = true;
  confirmDelete.error = "";
  try {
    await api.remove("Archive Document", name.value);
    toast("Đã xóa văn bản");
    const parent = overview.value.ancestors.at(-1);
    router.replace(parent ? `/ho-so/${encodeURIComponent(parent.name)}` : "/bien-muc");
  } catch (e) {
    confirmDelete.error = e.message;
  } finally {
    confirmDelete.busy = false;
  }
}
const downloadUrl = computed(() => preview.value?.download_url);
</script>

<template>
  <div v-if="loading" class="flex items-center gap-2 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải văn bản...</div>
  <EmptyState v-else-if="error" icon="alert-triangle" title="Không mở được văn bản" :text="error">
    <RouterLink class="btn no-underline" to="/bien-muc">Về trang Biên mục</RouterLink>
  </EmptyState>

  <template v-else-if="meta && overview">
    <Breadcrumbs :items="overview.ancestors" />
    <header class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="m-0 text-xl font-semibold tracking-tight">{{ record.document_title }}</h1>
        <p class="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span>{{ name }}</span>
          <span v-if="info.type" class="badge badge-info">{{ info.type }}</span>
          <StatusBadge :value="info.index_status" />
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <a v-for="entry in printEntries" :key="entry.view" class="btn no-underline" :href="entry.view" target="_blank" rel="noopener"><Icon name="printer" :size="16" /> In phiếu</a>
        <a v-if="downloadUrl" class="btn no-underline" :href="downloadUrl"><Icon name="download" :size="16" /> Tải tệp gốc</a>
        <button v-if="canWrite" class="btn" type="button" @click="replaceOpen = true"><Icon name="upload" :size="16" /> {{ info.attached ? "Thay tệp" : "Tải tệp lên" }}</button>
        <button v-if="overview.permissions.delete" class="btn text-danger" type="button" @click="confirmDelete.open = true"><Icon name="trash-2" :size="16" /> Xóa</button>
      </div>
    </header>

    <div class="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,1fr)]">
      <section class="card p-4">
        <DocumentPreview :preview="preview" :attached="info.attached" :loading="previewLoading" :error="previewError" />
      </section>

      <div class="space-y-5">
        <section class="card p-5">
          <h2 class="m-0 mb-4 text-sm font-semibold">Thông tin văn bản</h2>
          <p v-if="saveError" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ saveError }}</p>
          <FormRenderer :meta="meta" :record="record" :errors="fieldErrors" editing :read-only="!canWrite" />
          <div v-if="canWrite" class="mt-5 flex justify-end gap-2">
            <button class="btn" type="button" :disabled="!dirty || saving" @click="assign(JSON.parse(original))">Hoàn tác</button>
            <button class="btn btn-primary" type="button" :disabled="!dirty || saving" @click="save"><Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> Lưu</button>
          </div>
        </section>

        <section class="card p-5">
          <h2 class="m-0 mb-3 text-sm font-semibold">Tệp đính kèm</h2>
          <dl v-if="info.attached" class="m-0 space-y-2 text-sm">
            <div class="flex justify-between gap-3"><dt class="text-ink-muted">Tên tệp</dt><dd class="m-0 truncate text-right font-medium" :title="info.name">{{ info.name }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="text-ink-muted">Dung lượng</dt><dd class="m-0 font-medium">{{ info.size_kb ? formatSize(info.size_kb * 1024) : "—" }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="text-ink-muted">Đã lưu kho an toàn</dt><dd class="m-0 font-medium">{{ info.stored ? "Có" : "Chưa" }}</dd></div>
            <div class="flex justify-between gap-3"><dt class="text-ink-muted">Trích xuất nội dung</dt><dd class="m-0 font-medium">{{ info.has_text ? "Có" : "Không" }}</dd></div>
            <div v-if="info.checksum" class="flex justify-between gap-3"><dt class="text-ink-muted">SHA-256</dt><dd class="m-0 font-mono text-xs" :title="info.checksum">{{ info.checksum.slice(0, 16) }}…</dd></div>
            <div v-if="info.last_accessed" class="flex justify-between gap-3"><dt class="text-ink-muted">Truy cập gần nhất</dt><dd class="m-0 font-medium">{{ formatDateTime(info.last_accessed) }}</dd></div>
          </dl>
          <p v-else class="m-0 text-sm text-ink-muted">Chưa có tệp.</p>
          <button v-if="canWrite && info.attached && info.index_status === 'Lỗi'" class="btn mt-4" type="button" @click="reindex"><Icon name="refresh-cw" :size="16" /> Xử lý lại tệp</button>
        </section>
      </div>
    </div>

    <Drawer :open="replaceOpen" :title="info.attached ? 'Thay tệp của văn bản' : 'Tải tệp lên văn bản'" width="520px" @close="replaceOpen = false">
      <FileUploader mode="replace" :rules="overview.upload" :document="name" @done="afterReplace" />
    </Drawer>
    <ConfirmDialog
      :open="confirmDelete.open" danger title="Xóa văn bản" :message="`Xóa văn bản “${record.document_title}” cùng tệp đính kèm? Thao tác này không thể hoàn tác.`"
      :error="confirmDelete.error" confirm-text="Xóa" :busy="confirmDelete.busy" @confirm="remove" @cancel="confirmDelete.open = false"
    />
  </template>
</template>
