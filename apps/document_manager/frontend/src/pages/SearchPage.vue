<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import LinkSelect from "../components/LinkSelect.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { describe, fieldByName } from "../lib/doctype.js";
import { formatDate, formatNumber } from "../lib/format.js";
import { pageTitle } from "../lib/page.js";
import {
  SORTS, TABS, deleteSaved, emptyState, fromQuery, hasCriteria, loadSaved, safeHighlight, saveFilter, toApiParams, toQuery,
} from "../lib/searchState.js";
import { toast } from "../lib/toast.js";

// Basic and advanced search of archival files (hồ sơ) and documents (văn bản). The URL holds the whole
// search, so a result page can be bookmarked, shared and reached again with the Back button.
const route = useRoute();
const router = useRouter();
const PAGE_SIZE = 20;
const FILE_TYPES = ["PDF", "DOCX", "XLSX", "JPG", "PNG", "TIFF", "Khác"];

const state = reactive(fromQuery(route.query));
const result = reactive({ rows: [], total: 0, capped: false, engine: "", loading: false, error: "", done: false });
const fileMeta = ref(null);
const statuses = ref([]);
const saved = ref(loadSaved());
let ticket = 0;

const filters = computed(() => state.filters);
function setFilter(name, value) {
  if (value) state.filters[name] = value;
  else delete state.filters[name];
}

async function run() {
  const mine = ++ticket;
  result.loading = true;
  result.error = "";
  try {
    const call = state.tab === "ho-so" ? api.search.files : api.search.documents;
    const data = await call(toApiParams(state, PAGE_SIZE));
    if (mine !== ticket) return;
    Object.assign(result, { rows: data.data, total: data.total, capped: Boolean(data.total_capped), engine: data.engine || "", done: true });
  } catch (e) {
    if (mine === ticket) Object.assign(result, { error: e.message, rows: [], total: 0, done: true });
  } finally {
    if (mine === ticket) result.loading = false;
  }
}

function go(overrides = {}) {
  Object.assign(state, overrides);
  router.push({ path: "/tim-kiem", query: toQuery(state) });
}
const submit = () => go({ page: 1 });
function switchTab(tab) {
  go({ tab, filters: {}, page: 1, advanced: false });
}
function reset() {
  go({ q: "", filters: {}, sort: "", page: 1 });
}

watch(() => route.query, (query) => { Object.assign(state, fromQuery(query)); run(); });
onMounted(async () => {
  pageTitle.value = "Tìm kiếm";
  const meta = await describe("Archival File").catch(() => null);
  fileMeta.value = meta;
  statuses.value = meta ? (fieldByName(meta, "status")?.options || "").split("\n").filter(Boolean) : [];
  run();
});

function saveCurrent() {
  const name = window.prompt("Đặt tên cho bộ lọc này");
  if (!name || !name.trim()) return;
  saved.value = saveFilter(name, state);
  toast("Đã lưu bộ lọc");
}
function applySaved(entry) {
  router.push({ path: "/tim-kiem", query: entry.query });
}
function removeSaved(entry) {
  saved.value = deleteSaved(entry.name);
}
const savedForTab = computed(() => saved.value);
const idOf = (row) => row.name || row.id;
const engineLabel = computed(() => (result.engine === "meilisearch" ? "Tìm theo nội dung" : "Tìm theo thông tin"));
const openFile = (row) => router.push(`/ho-so/${encodeURIComponent(row.name)}`);
const activeCount = computed(() => Object.keys(state.filters).length);
</script>

<template>
  <PageHeader title="Tìm kiếm" subtitle="Tìm hồ sơ hoặc văn bản theo từ khóa, nội dung tệp và các điều kiện nâng cao" />

  <div class="card mb-5 p-4">
    <div class="mb-4 flex flex-wrap items-center gap-2" role="tablist">
      <button v-for="(tab, key) in TABS" :key="key" class="btn" :class="state.tab === key ? 'btn-primary' : ''" type="button" role="tab" :aria-selected="state.tab === key" @click="switchTab(key)">
        <Icon :name="key === 'ho-so' ? 'folder' : 'file-text'" :size="16" /> {{ tab.label }}
      </button>
      <span class="flex-1"></span>
      <div v-if="savedForTab.length" class="flex flex-wrap items-center gap-1">
        <Icon name="bookmark" :size="15" class="text-ink-muted" />
        <span v-for="entry in savedForTab" :key="entry.name" class="badge badge-info gap-1">
          <button type="button" class="font-medium" :title="`Áp dụng bộ lọc ${entry.name}`" @click="applySaved(entry)">{{ entry.name }}</button>
          <button type="button" :aria-label="`Xóa bộ lọc ${entry.name}`" @click="removeSaved(entry)"><Icon name="x" :size="12" /></button>
        </span>
      </div>
    </div>

    <form class="flex flex-wrap gap-2" @submit.prevent="submit">
      <div class="relative min-w-[240px] flex-1">
        <Icon name="search" :size="18" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
        <input v-model="state.q" class="input pl-10" type="search" :placeholder="state.tab === 'ho-so' ? 'Tên hồ sơ, số hồ sơ...' : 'Từ khóa trong tiêu đề, số ký hiệu, tác giả, nội dung tệp...'" aria-label="Từ khóa" />
      </div>
      <button class="btn btn-primary" type="submit"><Icon name="search" :size="16" /> Tìm kiếm</button>
      <button class="btn" type="button" :aria-expanded="state.advanced" @click="state.advanced = !state.advanced">
        <Icon name="sliders" :size="16" /> Nâng cao<span v-if="activeCount" class="badge badge-info">{{ activeCount }}</span>
      </button>
    </form>

    <form v-if="state.advanced" class="mt-4 border-t border-line pt-4" @submit.prevent="submit">
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div><label class="label" for="s-fonds">Phông</label><LinkSelect input-id="s-fonds" :model-value="filters.fonds || ''" doctype="Fonds" @update:model-value="setFilter('fonds', $event)" /></div>
        <template v-if="state.tab === 'ho-so'">
          <div><label class="label" for="s-rg">Khối tài liệu</label><LinkSelect input-id="s-rg" :model-value="filters.record_group || ''" doctype="Record Group" :filters="filters.fonds ? { fonds: filters.fonds } : null" @update:model-value="setFilter('record_group', $event)" /></div>
          <div><label class="label" for="s-cat">Mục lục</label><LinkSelect input-id="s-cat" :model-value="filters.catalog || ''" doctype="Catalog" :filters="filters.record_group ? { record_group: filters.record_group } : null" @update:model-value="setFilter('catalog', $event)" /></div>
          <div><label class="label" for="s-title">Tên hồ sơ</label><input id="s-title" class="input" :value="filters.file_title || ''" @input="setFilter('file_title', $event.target.value)" /></div>
          <div><label class="label" for="s-number">Số hồ sơ</label><input id="s-number" class="input" :value="filters.file_number || ''" @input="setFilter('file_number', $event.target.value)" /></div>
          <div>
            <label class="label" for="s-status">Trạng thái</label>
            <select id="s-status" class="input" :value="filters.status || ''" @change="setFilter('status', $event.target.value)">
              <option value="">Tất cả</option><option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
            </select>
          </div>
          <div><label class="label" for="s-wh">Kho lưu trữ</label><LinkSelect input-id="s-wh" :model-value="filters.storage_warehouse || ''" doctype="Storage Warehouse" @update:model-value="setFilter('storage_warehouse', $event)" /></div>
          <div><label class="label" for="s-d1">Bắt đầu từ ngày</label><input id="s-d1" class="input" type="date" :value="filters.start_date_from || ''" @input="setFilter('start_date_from', $event.target.value)" /></div>
          <div><label class="label" for="s-d2">Bắt đầu đến ngày</label><input id="s-d2" class="input" type="date" :value="filters.start_date_to || ''" @input="setFilter('start_date_to', $event.target.value)" /></div>
        </template>
        <template v-else>
          <div><label class="label" for="s-file">Hồ sơ</label><LinkSelect input-id="s-file" :model-value="filters.archival_file || ''" doctype="Archival File" :filters="filters.fonds ? { fonds: filters.fonds } : null" @update:model-value="setFilter('archival_file', $event)" /></div>
          <div>
            <label class="label" for="s-type">Loại tệp</label>
            <select id="s-type" class="input" :value="filters.file_type || ''" @change="setFilter('file_type', $event.target.value)">
              <option value="">Tất cả</option><option v-for="t in FILE_TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div><label class="label" for="s-dtitle">Tiêu đề văn bản</label><input id="s-dtitle" class="input" :value="filters.document_title || ''" @input="setFilter('document_title', $event.target.value)" /></div>
          <div><label class="label" for="s-dnum">Số, ký hiệu</label><input id="s-dnum" class="input" :value="filters.document_number || ''" @input="setFilter('document_number', $event.target.value)" /></div>
          <div><label class="label" for="s-author">Tác giả, cơ quan ban hành</label><input id="s-author" class="input" :value="filters.author || ''" @input="setFilter('author', $event.target.value)" /></div>
          <div><label class="label" for="s-dd1">Văn bản từ ngày</label><input id="s-dd1" class="input" type="date" :value="filters.date_from || ''" @input="setFilter('date_from', $event.target.value)" /></div>
          <div><label class="label" for="s-dd2">Văn bản đến ngày</label><input id="s-dd2" class="input" type="date" :value="filters.date_to || ''" @input="setFilter('date_to', $event.target.value)" /></div>
        </template>
        <div><label class="label" for="s-conf">Mức độ mật</label><LinkSelect input-id="s-conf" :model-value="filters.confidentiality_level || ''" doctype="Confidentiality Level" @update:model-value="setFilter('confidentiality_level', $event)" /></div>
      </div>
      <div class="mt-4 flex flex-wrap items-center justify-end gap-2">
        <button class="btn" type="button" :disabled="!hasCriteria(state)" @click="saveCurrent"><Icon name="bookmark" :size="16" /> Lưu bộ lọc</button>
        <button class="btn" type="button" @click="reset">Xóa điều kiện</button>
        <button class="btn btn-primary" type="submit"><Icon name="search" :size="16" /> Áp dụng</button>
      </div>
    </form>
  </div>

  <section class="card overflow-hidden" aria-live="polite">
    <div class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
      <h2 class="m-0 flex-1 text-sm font-semibold">
        <template v-if="result.loading">Đang tìm...</template>
        <template v-else-if="result.done">{{ formatNumber(result.total) }}{{ result.capped ? "+" : "" }} kết quả</template>
      </h2>
      <span v-if="result.engine && !result.loading" class="badge" :class="result.engine === 'meilisearch' ? 'badge-success' : 'badge-muted'">{{ engineLabel }}</span>
      <label class="sr-only" for="s-sort">Sắp xếp</label>
      <select id="s-sort" class="input w-44" :value="state.sort" @change="go({ sort: $event.target.value, page: 1 })">
        <option v-for="s in SORTS" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
    </div>
    <p v-if="result.error" class="m-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ result.error }}</p>
    <EmptyState v-else-if="result.done && !result.rows.length && !result.loading" icon="search" title="Không có kết quả" text="Thử từ khóa khác, bớt điều kiện lọc, hoặc kiểm tra mức độ mật được phép xem." />

    <template v-else-if="state.tab === 'ho-so' && fileMeta && result.rows.length">
      <DataTable :meta="fileMeta" :rows="result.rows" :loading="result.loading" @open="openFile" @sort="() => {}" />
    </template>

    <ul v-else-if="result.rows.length" class="m-0 list-none divide-y divide-line p-0" :class="{ 'opacity-60': result.loading }">
      <li v-for="row in result.rows" :key="idOf(row)" class="px-5 py-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <RouterLink class="text-base font-medium" :to="`/van-ban/${encodeURIComponent(idOf(row))}`" v-html="safeHighlight(row._formatted?.document_title || row.document_title || idOf(row))"></RouterLink>
          <span v-if="row.file_type" class="badge badge-info">{{ row.file_type }}</span>
        </div>
        <p class="m-0 mt-1 text-xs text-ink-muted">
          {{ idOf(row) }}<template v-if="row.document_number"> · Số {{ row.document_number }}</template><template v-if="row.document_date"> · {{ formatDate(row.document_date) }}</template><template v-if="row.author"> · {{ row.author }}</template>
          <template v-if="row.archival_file_title || row.archival_file"> · Hồ sơ: <RouterLink :to="`/ho-so/${encodeURIComponent(row.archival_file)}`">{{ row.archival_file_title || row.archival_file }}</RouterLink></template>
          <StatusBadge v-if="row.confidentiality_level && row.confidentiality_level !== 'Thường'" :value="row.confidentiality_level" class="ml-1" />
        </p>
        <p v-if="row._formatted?.content_text" class="m-0 mt-2 text-sm text-ink-soft" v-html="safeHighlight(row._formatted.content_text)"></p>
      </li>
    </ul>
    <PaginationBar v-if="result.rows.length" :page="state.page" :page-size="PAGE_SIZE" :total="result.total" :capped="result.capped" @change="(p) => go({ page: p })" />
  </section>
</template>
