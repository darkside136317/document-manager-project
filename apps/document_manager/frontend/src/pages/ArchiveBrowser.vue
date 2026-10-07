<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ArchiveTreeNode from "../components/ArchiveTreeNode.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import RecordDrawer from "../components/RecordDrawer.vue";
import { api } from "../lib/api.js";
import { describe } from "../lib/doctype.js";
import { debounce } from "../lib/format.js";
import { pageTitle } from "../lib/page.js";
import { nodeKey, useArchiveTree } from "../lib/useArchiveTree.js";

// The cataloguing workspace: the fonds > record group > catalog tree on the left, the archival files
// of the selected node on the right. Record groups, catalogs and files are created and edited here.
const route = useRoute();
const router = useRouter();
const tree = useArchiveTree();
const metas = reactive({});
const selected = ref(null); // {doctype, name, title}
const PAGE_SIZE = 20;
const files = reactive({ rows: [], total: 0, page: 1, search: "", sort: "modified desc", loading: true, error: "" });
const drawer = reactive({ open: false, doctype: "Archival File", name: null, defaults: {} });
let ticket = 0;

const FILTER_FIELD = { Fonds: "fonds", "Record Group": "record_group", Catalog: "catalog" };
const DOCTYPES = ["Fonds", "Record Group", "Catalog", "Archival File"];
const LABEL = { Fonds: "phông", "Record Group": "khối tài liệu", Catalog: "mục lục" };
const selectedKey = computed(() => nodeKey(selected.value));
const fileMeta = computed(() => metas["Archival File"]);
const can = (doctype, ptype) => Boolean(metas[doctype]?.permissions[ptype]);
const roots = computed(() => tree.children[""] || []);

async function loadFiles() {
  const mine = ++ticket;
  files.loading = true;
  files.error = "";
  const filters = selected.value ? { [FILTER_FIELD[selected.value.doctype]]: selected.value.name } : {};
  try {
    const result = await api.list("Archival File", { filters, search: files.search, order_by: files.sort, page: files.page, page_size: PAGE_SIZE });
    if (mine !== ticket) return;
    files.rows = result.data;
    files.total = result.total;
  } catch (e) {
    if (mine === ticket) files.error = e.message;
  } finally {
    if (mine === ticket) files.loading = false;
  }
}
const searchSoon = debounce(() => { files.page = 1; loadFiles(); }, 300);
onBeforeUnmount(() => searchSoon.cancel());

function select(node) {
  selected.value = node ? { doctype: node.doctype, name: node.name, title: node.title } : null;
  files.page = 1;
  router.replace({ path: "/bien-muc", query: node ? { node: nodeKey(node) } : {} });
  loadFiles();
}

/** ?node=Catalog:CAT-1 -> open the tree down to it and select it. */
async function selectFromQuery() {
  const raw = String(route.query.node || "");
  const [doctype, ...rest] = raw.split(":");
  const name = rest.join(":");
  if (!FILTER_FIELD[doctype] || !name) {
    selected.value = null;
    return loadFiles();
  }
  try {
    const record = await api.get(doctype, name);
    const chain = [];
    if (doctype !== "Fonds" && record.fonds) chain.push({ doctype: "Fonds", name: record.fonds });
    if (doctype === "Catalog" && record.record_group) chain.push({ doctype: "Record Group", name: record.record_group });
    if (doctype !== "Catalog") chain.push({ doctype, name });
    await tree.reveal(chain);
    const title = record.fonds_name || record.group_title || record.catalog_title || name;
    selected.value = { doctype, name, title };
  } catch {
    selected.value = null;
  }
  await loadFiles();
}

onMounted(async () => {
  pageTitle.value = "Biên mục hồ sơ, văn bản";
  await Promise.all(DOCTYPES.map(async (d) => (metas[d] = await describe(d).catch(() => null))));
  await tree.load(null);
  await selectFromQuery();
});
watch(() => route.query.node, (value) => { if (String(value || "") !== selectedKey.value) selectFromQuery(); });

function openDrawer(doctype, name = null, defaults = {}) {
  Object.assign(drawer, { open: true, doctype, name, defaults });
}
function addFile() {
  const sel = selected.value;
  const defaults = {};
  if (sel?.doctype === "Catalog") defaults.catalog = sel.name;
  openDrawer("Archival File", null, defaults);
}
function addChildNode() {
  const sel = selected.value;
  if (sel.doctype === "Fonds") openDrawer("Record Group", null, { fonds: sel.name });
  else openDrawer("Catalog", null, { record_group: sel.name });
}
async function afterSave(saved) {
  drawer.open = false;
  if (drawer.doctype === "Archival File" && !drawer.name) return router.push(`/ho-so/${encodeURIComponent(saved.name)}`);
  await tree.refresh();
  if (drawer.name && selected.value?.name === drawer.name) selected.value.title = saved[metas[drawer.doctype].title_field] || selected.value.title;
  await loadFiles();
}
async function afterDelete() {
  drawer.open = false;
  if (selected.value && selected.value.name === drawer.name) select(null);
  await tree.refresh();
  await loadFiles();
}
function onSort(field) {
  files.sort = files.sort === `${field} asc` ? `${field} desc` : `${field} asc`;
  files.page = 1;
  loadFiles();
}
const openFile = (row) => router.push(`/ho-so/${encodeURIComponent(row.name)}`);
// the parent of a catalog is a record group (and so on): offer only what belongs together
const linkFilters = (field, record) => (field.fieldname === "record_group" && record.fonds ? { fonds: record.fonds } : null);
</script>

<template>
  <PageHeader title="Biên mục hồ sơ, văn bản" subtitle="Phông › khối tài liệu › mục lục › hồ sơ › văn bản">
    <RouterLink class="btn no-underline" to="/tim-kiem"><Icon name="search" :size="16" /> Tìm kiếm</RouterLink>
    <button v-if="can('Archival File', 'create')" class="btn btn-primary" type="button" @click="addFile"><Icon name="plus" :size="16" /> Thêm hồ sơ</button>
  </PageHeader>

  <div class="grid grid-cols-1 gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
    <aside class="card h-fit p-2 lg:sticky lg:top-20">
      <button
        class="mb-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-semibold"
        :class="!selected ? 'bg-primary-soft' : 'hover:bg-surface-muted'"
        type="button"
        @click="select(null)"
      ><Icon name="folder-tree" :size="16" /> Tất cả hồ sơ</button>
      <p v-if="tree.state.error" class="m-2 rounded bg-danger-soft px-2 py-1 text-xs text-danger" role="alert">{{ tree.state.error }}</p>
      <div v-if="tree.loading[''] && !roots.length" class="flex items-center gap-2 px-3 py-4 text-sm text-ink-muted"><Icon name="loader" spin :size="16" /> Đang tải...</div>
      <p v-else-if="!roots.length" class="px-3 py-4 text-sm text-ink-muted">Chưa có phông nào. Tạo phông ở mục Danh mục.</p>
      <ul v-else class="m-0 list-none p-0" role="tree" aria-label="Phông, khối tài liệu, mục lục">
        <ArchiveTreeNode v-for="node in roots" :key="nodeKey(node)" :node="node" :tree="tree" :selected="selectedKey" @select="select" />
      </ul>
    </aside>

    <section class="min-w-0">
      <div v-if="selected" class="card mb-4 flex flex-wrap items-center gap-3 px-4 py-3">
        <Icon :name="selected.doctype === 'Fonds' ? 'library' : selected.doctype === 'Catalog' ? 'book-open-text' : 'layers'" class="text-ink-muted" />
        <div class="min-w-0 flex-1">
          <p class="m-0 text-xs uppercase tracking-wide text-ink-muted">{{ LABEL[selected.doctype] }}</p>
          <h2 class="m-0 truncate text-base font-semibold">{{ selected.title }}</h2>
        </div>
        <RouterLink v-if="selected.doctype === 'Fonds'" class="btn no-underline" to="/danh-muc/phong-luu-tru"><Icon name="external-link" :size="16" /> Quản lý phông</RouterLink>
        <button v-if="selected.doctype !== 'Fonds' && can(selected.doctype, 'write')" class="btn" type="button" @click="openDrawer(selected.doctype, selected.name)"><Icon name="pencil" :size="16" /> Sửa</button>
        <button v-if="selected.doctype !== 'Catalog' && can(selected.doctype === 'Fonds' ? 'Record Group' : 'Catalog', 'create')" class="btn" type="button" @click="addChildNode">
          <Icon name="plus" :size="16" /> {{ selected.doctype === "Fonds" ? "Thêm khối tài liệu" : "Thêm mục lục" }}
        </button>
      </div>

      <div class="card overflow-hidden">
        <div class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <h2 class="m-0 flex-1 text-sm font-semibold">Hồ sơ{{ selected ? ` trong ${LABEL[selected.doctype]} này` : "" }} <span class="font-normal text-ink-muted">({{ files.total }})</span></h2>
          <div class="relative">
            <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
            <input v-model="files.search" class="input w-60 pl-9" type="search" placeholder="Tìm hồ sơ..." aria-label="Tìm hồ sơ trong mục này" @input="searchSoon" />
          </div>
        </div>
        <p v-if="files.error" class="m-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ files.error }}</p>
        <div v-if="files.loading && !files.rows.length" class="flex items-center gap-2 px-5 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
        <EmptyState v-else-if="!files.rows.length" icon="folder" :title="files.search ? 'Không có hồ sơ khớp' : 'Chưa có hồ sơ'" :text="selected?.doctype === 'Catalog' ? 'Thêm hồ sơ đầu tiên vào mục lục này.' : ''">
          <button v-if="can('Archival File', 'create') && !files.search" class="btn btn-primary" type="button" @click="addFile"><Icon name="plus" :size="16" /> Thêm hồ sơ</button>
        </EmptyState>
        <template v-else-if="fileMeta">
          <DataTable :meta="fileMeta" :rows="files.rows" :loading="files.loading" :sort="files.sort" @open="openFile" @sort="onSort" />
          <PaginationBar :page="files.page" :page-size="PAGE_SIZE" :total="files.total" @change="(p) => { files.page = p; loadFiles(); }" />
        </template>
      </div>
    </section>
  </div>

  <RecordDrawer
    v-if="metas[drawer.doctype]"
    :open="drawer.open"
    :meta="metas[drawer.doctype]"
    :name="drawer.name"
    :defaults="drawer.defaults"
    :link-filters="linkFilters"
    @close="drawer.open = false"
    @saved="afterSave"
    @deleted="afterDelete"
  />
</template>
