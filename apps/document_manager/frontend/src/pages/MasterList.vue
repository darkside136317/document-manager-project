<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import RecordDrawer from "../components/RecordDrawer.vue";
import { api } from "../lib/api.js";
import { debounce } from "../lib/format.js";

// Flat list of one registered DocType: search, sort, pages, create/edit/delete in a drawer.
const props = defineProps({ meta: { type: Object, required: true } });

const PAGE_SIZE = 20;
const state = reactive({ rows: [], total: 0, capped: false, page: 1, search: "", sort: "modified desc", loading: true, error: "" });
const drawer = reactive({ open: false, name: null });
let ticket = 0;

async function load() {
  const mine = ++ticket;
  state.loading = true;
  state.error = "";
  try {
    const result = await api.list(props.meta.doctype, {
      search: state.search, order_by: state.sort, page: state.page, page_size: PAGE_SIZE,
    });
    if (mine !== ticket) return;
    state.rows = result.data;
    state.total = result.total;
    state.capped = Boolean(result.total_capped);
  } catch (e) {
    if (mine === ticket) state.error = e.message;
  } finally {
    if (mine === ticket) state.loading = false;
  }
}
const searchSoon = debounce(() => { state.page = 1; load(); }, 300);
onMounted(load);
onBeforeUnmount(() => searchSoon.cancel());

function onSort(field) {
  state.sort = state.sort === `${field} asc` ? `${field} desc` : `${field} asc`;
  state.page = 1;
  load();
}
function openRecord(row) { Object.assign(drawer, { open: true, name: row.name }); }
function openNew() { Object.assign(drawer, { open: true, name: null }); }
function closeDrawer() { drawer.open = false; }
async function afterChange() {
  closeDrawer();
  await load();
}
</script>

<template>
  <PageHeader :title="meta.label">
    <div class="relative">
      <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
      <input v-model="state.search" class="input w-64 pl-9" type="search" :placeholder="`Tìm ${meta.label.toLowerCase()}...`" aria-label="Tìm kiếm" @input="searchSoon" />
    </div>
    <button v-if="meta.permissions.create" class="btn btn-primary" type="button" @click="openNew"><Icon name="plus" :size="16" /> Thêm mới</button>
  </PageHeader>

  <p v-if="state.error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ state.error }}</p>

  <section class="card overflow-hidden">
    <div v-if="state.loading && !state.rows.length" class="flex items-center gap-2 px-5 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <EmptyState
      v-else-if="!state.rows.length"
      icon="inbox"
      :title="state.search ? 'Không tìm thấy kết quả' : `Chưa có ${meta.label.toLowerCase()}`"
      :text="state.search ? 'Thử từ khóa khác hoặc xóa bộ lọc.' : ''"
    >
      <button v-if="meta.permissions.create && !state.search" class="btn btn-primary" type="button" @click="openNew"><Icon name="plus" :size="16" /> Thêm mới</button>
    </EmptyState>
    <template v-else>
      <DataTable :meta="meta" :rows="state.rows" :loading="state.loading" :sort="state.sort" @open="openRecord" @sort="onSort" />
      <PaginationBar :page="state.page" :page-size="PAGE_SIZE" :total="state.total" :capped="state.capped" @change="(p) => { state.page = p; load(); }" />
    </template>
  </section>

  <RecordDrawer :open="drawer.open" :meta="meta" :name="drawer.name" @close="closeDrawer" @saved="afterChange" @deleted="afterChange" />
</template>
