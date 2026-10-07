<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import Breadcrumbs from "../components/Breadcrumbs.vue";
import DataTable from "../components/DataTable.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import FileUploader from "../components/FileUploader.vue";
import Icon from "../components/Icon.vue";
import PaginationBar from "../components/PaginationBar.vue";
import RecordDrawer from "../components/RecordDrawer.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { describe } from "../lib/doctype.js";
import { debounce, displayValue, formatDate, formatNumber } from "../lib/format.js";
import { pageTitle } from "../lib/page.js";
import { formatSize } from "../lib/upload.js";

// One archival file: its description, the documents inside, uploading files into it, printing.
const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));
const PAGE_SIZE = 20;

const file = ref(null);
const overview = ref(null);
const fileMeta = ref(null);
const documentMeta = ref(null);
const error = ref("");
const loading = ref(true);
const docs = reactive({ rows: [], total: 0, page: 1, search: "", sort: "document_date asc", loading: false, error: "" });
const edit = reactive({ open: false });
const addDocument = reactive({ open: false });
const upload = reactive({ open: false });
const printOpen = ref(false);
let ticket = 0;
let refreshTimer = null;
let pollUntil = 0; // after an upload, keep looking for a minute: the jobs start a moment later

const canWrite = computed(() => overview.value?.permissions.write);
const canAdd = computed(() => overview.value?.permissions.add_documents);

async function loadDocuments() {
  const mine = ++ticket;
  docs.loading = true;
  docs.error = "";
  try {
    const result = await api.list("Archive Document", {
      filters: { archival_file: name.value }, search: docs.search, order_by: docs.sort, page: docs.page, page_size: PAGE_SIZE,
    });
    if (mine !== ticket) return;
    docs.rows = result.data;
    docs.total = result.total;
  } catch (e) {
    if (mine === ticket) docs.error = e.message;
  } finally {
    if (mine === ticket) docs.loading = false;
  }
}
const searchSoon = debounce(() => { docs.page = 1; loadDocuments(); }, 300);

async function loadFile() {
  loading.value = true;
  error.value = "";
  try {
    [file.value, overview.value, fileMeta.value, documentMeta.value] = await Promise.all([
      api.get("Archival File", name.value), api.archive.fileOverview(name.value),
      describe("Archival File"), describe("Archive Document"),
    ]);
    pageTitle.value = file.value.file_title || name.value;
    await loadDocuments();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
// Files being processed in the background (text extraction, indexing) change state on their own.
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    if (docs.rows.some((r) => r.search_index_status === "Đang xử lý") || Date.now() < pollUntil) {
      await Promise.all([loadDocuments(), api.archive.fileOverview(name.value).then((o) => (overview.value = o))]);
      scheduleRefresh();
    }
  }, 4000);
}
watch(() => docs.rows, scheduleRefresh);
onMounted(loadFile);
onBeforeUnmount(() => { clearTimeout(refreshTimer); searchSoon.cancel(); });
watch(name, loadFile);

const summary = computed(() => {
  const f = file.value;
  if (!f) return [];
  return [
    ["Số hồ sơ", f.file_number], ["Thời gian", [formatDate(f.start_date), formatDate(f.end_date)].filter(Boolean).join(" — ")],
    ["Số tờ", f.total_pages ? formatNumber(f.total_pages) : ""], ["Mức độ mật", f.confidentiality_level],
    ["Kho lưu trữ", f.storage_warehouse], ["Giá / Hộp", [f.shelf_number, f.box_number].filter(Boolean).join(" / ")],
    ["Vị trí vật lý", f.physical_location], ["Thời hạn bảo quản", f.retention_years ? `${f.retention_years} năm` : ""],
    ["Loại hình", f.document_type_category], ["Nhóm tài liệu", f.document_group], ["Khung phân loại", f.classification_scheme],
  ].filter(([, v]) => v);
});

function onSort(field) {
  docs.sort = docs.sort === `${field} asc` ? `${field} desc` : `${field} asc`;
  docs.page = 1;
  loadDocuments();
}
const openDoc = (row) => router.push(`/van-ban/${encodeURIComponent(row.name)}`);
async function afterEdit() {
  edit.open = false;
  await loadFile();
}
async function afterDelete() {
  edit.open = false;
  const parent = overview.value.ancestors.at(-1);
  router.replace(parent ? { path: "/bien-muc", query: { node: `${parent.doctype}:${parent.name}` } } : "/bien-muc");
}
async function afterAddDocument(saved) {
  addDocument.open = false;
  router.push(`/van-ban/${encodeURIComponent(saved.name)}`);
}
async function afterUpload() {
  pollUntil = Date.now() + 60000;
  await Promise.all([loadDocuments(), api.archive.fileOverview(name.value).then((o) => (overview.value = o)),
    api.get("Archival File", name.value).then((f) => (file.value = f))]);
}
const printEntries = computed(() => Object.entries(overview.value?.print || {}));
</script>

<template>
  <div v-if="loading" class="flex items-center gap-2 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải hồ sơ...</div>
  <EmptyState v-else-if="error" icon="alert-triangle" title="Không mở được hồ sơ" :text="error">
    <RouterLink class="btn no-underline" to="/bien-muc">Về trang Biên mục</RouterLink>
  </EmptyState>

  <template v-else-if="file">
    <Breadcrumbs :items="overview.ancestors" />
    <header class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="m-0 text-xl font-semibold tracking-tight">{{ file.file_title }}</h1>
        <p class="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span>{{ file.name }}</span><span v-if="file.file_number">· Số {{ file.file_number }}</span>
          <StatusBadge :value="file.status" /><StatusBadge v-if="file.disposal_status && file.disposal_status !== 'Bình thường'" :value="file.disposal_status" />
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div v-if="printEntries.length" class="relative">
          <button class="btn" type="button" aria-haspopup="menu" :aria-expanded="printOpen" @click="printOpen = !printOpen"><Icon name="printer" :size="16" /> In <Icon name="chevron-down" :size="14" /></button>
          <div v-if="printOpen" class="card absolute right-0 z-30 mt-1 w-64 py-1 shadow-pop" role="menu" @click="printOpen = false">
            <template v-for="[kind, entry] in printEntries" :key="kind">
              <a class="flex items-center gap-2 px-4 py-2 text-sm text-ink no-underline hover:bg-surface-muted" :href="entry.view" target="_blank" rel="noopener" role="menuitem"><Icon name="printer" :size="15" /> {{ entry.label }}</a>
              <a class="flex items-center gap-2 px-4 py-2 text-sm text-ink no-underline hover:bg-surface-muted" :href="entry.pdf" target="_blank" rel="noopener" role="menuitem"><Icon name="download" :size="15" /> {{ entry.label }} (PDF)</a>
            </template>
          </div>
        </div>
        <button v-if="canWrite" class="btn" type="button" @click="edit.open = true"><Icon name="pencil" :size="16" /> Sửa hồ sơ</button>
      </div>
    </header>

    <div class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div class="card px-4 py-3"><p class="m-0 text-2xl font-semibold">{{ formatNumber(overview.stats.documents) }}</p><p class="m-0 text-sm text-ink-muted">Văn bản</p></div>
      <div class="card px-4 py-3"><p class="m-0 text-2xl font-semibold">{{ formatSize(overview.stats.size_kb * 1024) }}</p><p class="m-0 text-sm text-ink-muted">Dung lượng tệp</p></div>
      <div class="card px-4 py-3"><p class="m-0 text-2xl font-semibold">{{ overview.stats.indexed }}/{{ overview.stats.documents }}</p><p class="m-0 text-sm text-ink-muted">Đã lập chỉ mục tìm kiếm</p></div>
      <div class="card px-4 py-3"><p class="m-0 text-2xl font-semibold" :class="overview.stats.failed ? 'text-danger' : ''">{{ overview.stats.failed }}</p><p class="m-0 text-sm text-ink-muted">Văn bản lỗi xử lý</p></div>
    </div>

    <section v-if="summary.length || file.description" class="card mb-5 p-5">
      <h2 class="m-0 mb-3 text-sm font-semibold">Thông tin hồ sơ</h2>
      <dl class="m-0 grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="[label, value] in summary" :key="label"><dt class="text-xs uppercase tracking-wide text-ink-muted">{{ label }}</dt><dd class="m-0 text-sm font-medium">{{ value }}</dd></div>
      </dl>
      <div v-if="file.description" class="mt-4 border-t border-line pt-3 text-sm" v-html="file.description"></div>
    </section>

    <section class="card overflow-hidden">
      <div class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <h2 class="m-0 flex-1 text-sm font-semibold">Văn bản trong hồ sơ <span class="font-normal text-ink-muted">({{ docs.total }})</span></h2>
        <div class="relative">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
          <input v-model="docs.search" class="input w-56 pl-9" type="search" placeholder="Tìm văn bản..." aria-label="Tìm văn bản trong hồ sơ" @input="searchSoon" />
        </div>
        <button v-if="canAdd" class="btn" type="button" @click="addDocument.open = true"><Icon name="plus" :size="16" /> Thêm văn bản</button>
        <button v-if="canAdd" class="btn btn-primary" type="button" @click="upload.open = true"><Icon name="upload" :size="16" /> Tải tệp lên</button>
      </div>
      <p v-if="docs.error" class="m-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ docs.error }}</p>
      <EmptyState v-if="!docs.rows.length && !docs.loading" icon="file-text" :title="docs.search ? 'Không có văn bản khớp' : 'Hồ sơ chưa có văn bản'" :text="docs.search ? '' : 'Tải các tệp PDF, Word, Excel hoặc ảnh quét lên: mỗi tệp trở thành một văn bản.'">
        <button v-if="canAdd && !docs.search" class="btn btn-primary" type="button" @click="upload.open = true"><Icon name="upload" :size="16" /> Tải tệp lên</button>
      </EmptyState>
      <template v-else-if="documentMeta">
        <DataTable :meta="documentMeta" :rows="docs.rows" :loading="docs.loading" :sort="docs.sort" @open="openDoc" @sort="onSort" />
        <PaginationBar :page="docs.page" :page-size="PAGE_SIZE" :total="docs.total" @change="(p) => { docs.page = p; loadDocuments(); }" />
      </template>
    </section>

    <RecordDrawer :open="edit.open" :meta="fileMeta" :name="name" @close="edit.open = false" @saved="afterEdit" @deleted="afterDelete" />
    <RecordDrawer :open="addDocument.open" :meta="documentMeta" :defaults="{ archival_file: name }" @close="addDocument.open = false" @saved="afterAddDocument" />
    <Drawer :open="upload.open" title="Tải tệp lên hồ sơ" width="560px" @close="upload.open = false">
      <FileUploader :rules="overview.upload" :archival-file="name" @done="afterUpload" />
    </Drawer>
  </template>
</template>
