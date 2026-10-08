<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BarChart from "../components/BarChart.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterForm from "../components/FilterForm.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import { api } from "../lib/api.js";
import { boot } from "../lib/boot.js";
import { pageTitle } from "../lib/page.js";
import { cleanFilters, diffClass, downloadUrl, formatCell, initialFilters, printUrl, routeOf, signed } from "../lib/reports.js";
import { formatNumber } from "../lib/format.js";

// One report: its filters (kept in the address, so a view can be shared), the result with totals and chart, and the
// ways out of it: Excel, CSV, a printable page and a PDF.
const props = defineProps({ slug: { type: String, required: true } });
const route = useRoute();
const router = useRouter();

const definition = ref(null);
const filters = ref({});
const result = ref(null);
const loading = ref(false);
const error = ref("");
const showFilters = ref(true);
const PAGE_SIZE = 50;

const page = computed(() => Math.max(1, Number(route.query.page) || 1));
const applied = computed(() => cleanFilters(filters.value));
const columns = computed(() => result.value?.columns || definition.value?.columns || []);
const hasInventory = computed(() => props.slug === "tong-kiem-ke" && boot.inventory?.length);

async function load() {
  if (!definition.value) return;
  loading.value = true;
  error.value = "";
  try {
    result.value = await api.reports.run(props.slug, applied.value, page.value, PAGE_SIZE);
  } catch (e) {
    error.value = e.message;
    result.value = null;
  } finally {
    loading.value = false;
  }
}

async function open() {
  definition.value = null;
  result.value = null;
  error.value = "";
  try {
    definition.value = await api.reports.get(props.slug);
  } catch (e) {
    error.value = e.message;
    return;
  }
  pageTitle.value = definition.value.title;
  filters.value = initialFilters(definition.value.filters, route.query);
  await load();
}
watch(() => props.slug, open, { immediate: true });
watch(() => route.query, (now, before) => { if (definition.value && JSON.stringify(now) !== JSON.stringify(before)) load(); });

function search() {
  router.replace({ query: { ...applied.value } });
  if (JSON.stringify(route.query) === JSON.stringify(applied.value)) load();
}
function reset() {
  filters.value = initialFilters(definition.value.filters);
  search();
}
function goto(next) {
  router.replace({ query: { ...applied.value, ...(next > 1 ? { page: next } : {}) } });
}

const isDiff = (column) => Boolean(column.diff);
const cell = (column, row) => (isDiff(column) ? signed(row[column.fieldname]) : formatCell(column, row[column.fieldname]));
</script>

<template>
  <EmptyState v-if="error && !definition" icon="alert-triangle" title="Không mở được báo cáo" :text="error">
    <RouterLink class="btn" to="/bao-cao">Về danh sách báo cáo</RouterLink>
  </EmptyState>

  <template v-else-if="definition">
    <nav class="mb-2 text-sm text-ink-muted" aria-label="Đường dẫn"><RouterLink to="/bao-cao">Thống kê, báo cáo</RouterLink> › {{ definition.group }}</nav>
    <PageHeader :title="definition.title" :subtitle="definition.description">
      <RouterLink v-if="hasInventory" class="btn" to="/kiem-ke"><Icon name="clipboard-check" :size="16" /> Quản lý đợt kiểm kê</RouterLink>
      <a class="btn" :href="downloadUrl(slug, applied, 'xlsx')"><Icon name="file-spreadsheet" :size="16" /> Excel</a>
      <a class="btn" :href="downloadUrl(slug, applied, 'csv')"><Icon name="download" :size="16" /> CSV</a>
      <a class="btn" :href="printUrl(slug, applied)" target="_blank" rel="noopener"><Icon name="printer" :size="16" /> In</a>
      <a class="btn" :href="printUrl(slug, applied, 'pdf')"><Icon name="file-down" :size="16" /> PDF</a>
    </PageHeader>

    <section v-if="definition.filters.length" class="card mb-5">
      <button class="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-semibold" type="button" :aria-expanded="showFilters" @click="showFilters = !showFilters">
        <span class="flex items-center gap-2"><Icon name="sliders" :size="16" /> Bộ lọc<span v-if="Object.keys(applied).length" class="badge badge-info">{{ Object.keys(applied).length }}</span></span>
        <Icon :name="showFilters ? 'chevron-down' : 'chevron-right'" :size="16" />
      </button>
      <div v-show="showFilters" class="border-t border-line px-5 py-4">
        <FilterForm v-model="filters" :filters="definition.filters" :busy="loading" submit-label="Xem báo cáo" @submit="search" @reset="reset" />
      </div>
    </section>

    <p v-if="error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

    <section v-if="result?.info?.length" class="card mb-5 grid gap-x-8 gap-y-1 px-5 py-4 text-sm sm:grid-cols-2">
      <p v-for="[label, value] in result.info" :key="label" class="m-0"><span class="text-ink-muted">{{ label }}:</span> <strong>{{ value }}</strong></p>
    </section>

    <section v-if="result?.chart" class="card mb-5 px-5 py-4"><BarChart :chart="result.chart" /></section>

    <section class="card">
      <div v-if="loading && !result" class="space-y-2 p-5"><div v-for="n in 6" :key="n" class="h-8 animate-pulse rounded bg-surface-muted"></div></div>
      <EmptyState v-else-if="result && !result.rows.length" icon="search" title="Không có dữ liệu" text="Không có bản ghi nào khớp với bộ lọc. Thử bớt điều kiện lọc." />
      <div v-else-if="result" class="table-wrap" :class="{ 'opacity-60': loading }">
        <table class="data-table">
          <caption class="sr-only">{{ definition.title }}</caption>
          <thead>
            <tr>
              <th v-if="result.paged" scope="col" class="w-12 text-right">STT</th>
              <th v-for="column in columns" :key="column.fieldname" scope="col" :class="{ 'text-right': column.align === 'right' }">{{ column.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in result.rows" :key="row.name || index">
              <td v-if="result.paged" class="text-right text-ink-subtle tabular-nums">{{ (result.page - 1) * result.page_size + index + 1 }}</td>
              <td v-for="column in columns" :key="column.fieldname" :class="[column.align === 'right' ? 'text-right tabular-nums' : '', isDiff(column) ? diffClass(row[column.fieldname]) : '']">
                <RouterLink v-if="routeOf(column, row)" :to="routeOf(column, row)">{{ cell(column, row) }}</RouterLink>
                <template v-else>{{ cell(column, row) }}</template>
              </td>
            </tr>
          </tbody>
          <tfoot v-if="result.summary">
            <tr class="font-semibold">
              <td v-if="result.paged"></td>
              <td v-for="column in columns" :key="column.fieldname" :class="[column.align === 'right' ? 'text-right tabular-nums' : '', isDiff(column) ? diffClass(result.summary[column.fieldname]) : '']">
                {{ isDiff(column) ? signed(result.summary[column.fieldname]) : formatCell(column, result.summary[column.fieldname]) }}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <PaginationBar v-if="result?.paged" :page="result.page" :page-size="result.page_size" :total="result.total" @change="goto" />
      <p v-else-if="result" class="m-0 border-t border-line px-4 py-3 text-sm text-ink-muted">{{ formatNumber(result.total) }} dòng</p>
    </section>
  </template>
</template>
