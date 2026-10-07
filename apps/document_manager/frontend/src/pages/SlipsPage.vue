<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import NewSlipDrawer from "../components/NewSlipDrawer.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { boot } from "../lib/boot.js";
import { debounce, formatDate, formatDateTime, truncate } from "../lib/format.js";
import { refreshBadges } from "../lib/registrations.js";
import { counter, dueText, kindOf, pickView } from "../lib/slips.js";

// The queue of one kind of slip: tabs by what has to be done next (receive, leader, hand over, in use, overdue,
// closed), a search box and the list. A row opens the slip.
const props = defineProps({ kind: { type: String, default: "usage" } });
const route = useRoute();
const router = useRouter();
const PAGE_SIZE = 20;

const info = computed(() => kindOf(props.kind));
const state = reactive({ rows: [], total: 0, page: 1, view: "", views: [], summary: null, search: "", loading: true, error: "", newOpen: false });
const canCreate = computed(() => boot.user.roles.some((r) => ["Reading Room Officer", "Document Admin"].includes(r)));
let ticket = 0;

const countFor = (view) => state.summary?.[props.kind]?.[view] ?? 0;

async function loadSummary() {
  try {
    state.summary = await api.slips.summary();
  } catch {
    /* the tabs work without their counters */
  }
}

async function load() {
  const mine = ++ticket;
  state.loading = true;
  state.error = "";
  try {
    const result = await api.slips.list(props.kind, { view: state.view, search: state.search, page: state.page, page_size: PAGE_SIZE });
    if (mine !== ticket) return;
    Object.assign(state, { rows: result.rows, total: result.total, views: result.views, view: result.view });
  } catch (e) {
    if (mine === ticket) state.error = e.message;
  } finally {
    if (mine === ticket) state.loading = false;
  }
}

async function start() {
  Object.assign(state, { rows: [], total: 0, page: 1, search: "", view: "", views: [], loading: true });
  await loadSummary();
  const fallback = state.summary?.default_view || "cho_tiep_nhan";
  const known = Object.keys(state.summary?.[props.kind] || {}).map((view) => ({ view }));
  state.view = pickView(route.query.view, known, fallback);
  await load();
}

function setView(view) {
  state.view = view;
  state.page = 1;
  router.replace({ query: { ...route.query, view } });
  load();
}
const searchSoon = debounce(() => { state.page = 1; load(); }, 300);
onMounted(start);
watch(() => props.kind, start);
onBeforeUnmount(() => searchSoon.cancel());

function open(row) {
  router.push(`${info.value.route}/${encodeURIComponent(row.name)}`);
}
async function created(name) {
  state.newOpen = false;
  await Promise.all([loadSummary(), refreshBadges(api.slips.badges)]);
  open({ name });
}
</script>

<template>
  <PageHeader :title="info.label" subtitle="Tiếp nhận, duyệt, giao – trả và theo dõi hạn trả của độc giả.">
    <div class="relative">
      <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
      <input v-model="state.search" class="input w-64 pl-9" type="search" placeholder="Tìm số phiếu, độc giả, mục đích..." aria-label="Tìm phiếu" @input="searchSoon" />
    </div>
    <button v-if="canCreate" class="btn btn-primary" type="button" @click="state.newOpen = true"><Icon name="plus" :size="16" /> Lập phiếu cho độc giả</button>
  </PageHeader>

  <div class="mb-4 flex flex-wrap gap-1" role="tablist" :aria-label="`Danh sách ${info.short}`">
    <button
      v-for="view in state.views" :key="view.view" type="button" role="tab" class="btn btn-sm"
      :class="{ 'btn-primary': state.view === view.view }" :aria-selected="state.view === view.view" @click="setView(view.view)"
    >
      {{ view.label }}
      <span v-if="counter(countFor(view.view))" class="rounded-full px-1.5 text-xs" :class="state.view === view.view ? 'bg-white/25' : 'bg-surface-muted text-ink-muted'">{{ counter(countFor(view.view)) }}</span>
    </button>
  </div>

  <p v-if="state.error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ state.error }}</p>

  <section class="card overflow-hidden">
    <div v-if="state.loading && !state.rows.length" class="flex items-center gap-2 px-5 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <EmptyState v-else-if="!state.rows.length" icon="inbox" :title="state.search ? 'Không tìm thấy phiếu phù hợp' : 'Không có phiếu nào ở mục này'" text="Phiếu mới của độc giả sẽ hiện ở “Chờ tiếp nhận”." />
    <template v-else>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Số phiếu</th><th scope="col">Độc giả</th><th scope="col">{{ info.purposeLabel }}</th><th scope="col">Số mục</th>
              <th scope="col">Gửi lúc</th><th v-if="kind === 'usage'" scope="col">Hạn trả</th><th scope="col">Trạng thái</th>
            </tr>
          </thead>
          <tbody :class="{ 'opacity-60': state.loading }">
            <tr v-for="row in state.rows" :key="row.name" class="is-clickable" tabindex="0" @click="open(row)" @keydown.enter="open(row)">
              <td class="whitespace-nowrap font-medium">{{ row.name }}</td>
              <td>{{ row.reader_name || row.reader }}</td>
              <td class="max-w-xs text-ink-soft">{{ truncate(row.purpose, 70) }}</td>
              <td>{{ row.item_count }}</td>
              <td class="whitespace-nowrap text-ink-soft">{{ formatDateTime(row.submitted_on || row.modified) }}</td>
              <td v-if="kind === 'usage'" class="whitespace-nowrap">
                {{ formatDate(row.due_date) }}
                <span v-if="dueText(row)" class="badge badge-danger ml-1">{{ dueText(row) }}</span>
              </td>
              <td class="whitespace-nowrap">
                <StatusBadge :value="row.workflow_state" />
                <span v-if="row.requires_leader && ['Chờ duyệt', 'Chờ lãnh đạo duyệt'].includes(row.workflow_state)" class="badge badge-muted ml-1">Cần lãnh đạo</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar :page="state.page" :page-size="PAGE_SIZE" :total="state.total" @change="(p) => { state.page = p; load(); }" />
    </template>
  </section>

  <NewSlipDrawer :open="state.newOpen" :kind="kind" @close="state.newOpen = false" @created="created" />
</template>
