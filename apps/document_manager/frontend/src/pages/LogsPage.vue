<script setup>
import { computed, onMounted, ref, watch } from "vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import { api } from "../lib/api.js";
import { cleanLogFilters, latestPurgeDate, logDownloadUrl, prettyJson, purgeConfirmed } from "../lib/admin.js";
import { debounce, formatDate, formatDateTime, formatNumber } from "../lib/format.js";
import { toast } from "../lib/toast.js";

// The system log: search and filter, read an entry, download the result, and the guarded clean-up of old entries.
const options = ref({ activity_types: [], users: [], doctypes: [] });
const filters = ref({ activity_type: "", user: "", reference_doctype: "", reference_name: "", search: "", date_from: "", date_to: "" });
const list = ref({ data: [], total: 0, page: 1, page_size: 50 });
const loading = ref(false);
const error = ref("");
const entry = ref(null);

const cleaning = ref(false);
const purge = ref({ before: "", types: [], preview: null, typed: "", busy: false, error: "" });
const maxDate = latestPurgeDate();
const canPurge = computed(() => purgeConfirmed(purge.value.typed, purge.value.preview?.total || 0) && !purge.value.busy);

let ticket = 0;
async function load(page = 1) {
  const mine = ++ticket; // an answer to a filter the user has since changed must not replace the list
  loading.value = true;
  try {
    const answer = await api.logs.list({ ...cleanLogFilters(filters.value), page });
    if (mine !== ticket) return;
    list.value = answer;
    error.value = "";
  } catch (e) {
    if (mine === ticket) error.value = e.message;
  } finally {
    if (mine === ticket) loading.value = false;
  }
}
const reload = debounce(() => load(1), 350);
watch(() => [filters.value.search, filters.value.reference_name], reload);
watch(() => [filters.value.activity_type, filters.value.user, filters.value.reference_doctype, filters.value.date_from, filters.value.date_to], () => load(1));
onMounted(async () => {
  api.logs.options().then((o) => { options.value = o; }).catch(() => {});
  load(1);
});

async function openEntry(row) {
  try {
    entry.value = await api.logs.get(row.name);
  } catch (e) {
    error.value = e.message;
  }
}
function reset() {
  filters.value = { activity_type: "", user: "", reference_doctype: "", reference_name: "", search: "", date_from: "", date_to: "" };
}

function openClean() {
  purge.value = { before: maxDate, types: [], preview: null, typed: "", busy: false, error: "" };
  cleaning.value = true;
}
async function preview() {
  purge.value.error = "";
  purge.value.preview = null;
  purge.value.typed = "";
  try {
    purge.value.preview = await api.logs.previewPurge(purge.value.before, purge.value.types.length ? purge.value.types : null);
  } catch (e) {
    purge.value.error = e.message;
  }
}
async function runPurge() {
  purge.value.busy = true;
  purge.value.error = "";
  try {
    const result = await api.logs.purge(purge.value.before, purge.value.preview.total, purge.value.types.length ? purge.value.types : null);
    toast(`Đã xóa ${formatNumber(result.deleted)} dòng nhật ký`);
    cleaning.value = false;
    await load(1);
  } catch (e) {
    purge.value.error = e.message;
  } finally {
    purge.value.busy = false;
  }
}
const toggleType = (type) => {
  purge.value.types = purge.value.types.includes(type) ? purge.value.types.filter((t) => t !== type) : [...purge.value.types, type];
  purge.value.preview = null;
};
</script>

<template>
  <PageHeader title="Nhật ký hệ thống" subtitle="Mọi thao tác quan trọng: đăng nhập, xem, sửa, xóa, xuất, nhập, sao lưu, phục hồi, quản lý người dùng.">
    <a class="btn" :href="logDownloadUrl(filters)"><Icon name="download" :size="16" /> Tải CSV</a>
    <button class="btn" type="button" @click="openClean"><Icon name="trash-2" :size="16" /> Dọn dẹp</button>
  </PageHeader>

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

  <section class="card mb-5 px-4 py-4">
    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <label class="text-sm xl:col-span-2"><span class="label">Tìm trong nội dung</span><input v-model="filters.search" class="input" type="search" placeholder="Từ khóa trong nội dung, mã đối tượng, người dùng" /></label>
      <label class="text-sm"><span class="label">Loại thao tác</span>
        <select v-model="filters.activity_type" class="input"><option value="">Tất cả</option><option v-for="t in options.activity_types" :key="t">{{ t }}</option></select></label>
      <label class="text-sm"><span class="label">Người dùng</span>
        <select v-model="filters.user" class="input"><option value="">Tất cả</option><option v-for="u in options.users" :key="u">{{ u }}</option></select></label>
      <label class="text-sm"><span class="label">Loại dữ liệu</span>
        <select v-model="filters.reference_doctype" class="input"><option value="">Tất cả</option><option v-for="d in options.doctypes" :key="d">{{ d }}</option></select></label>
      <label class="text-sm"><span class="label">Mã đối tượng</span><input v-model="filters.reference_name" class="input" type="text" /></label>
      <label class="text-sm"><span class="label">Từ ngày</span><input v-model="filters.date_from" class="input" type="date" /></label>
      <label class="text-sm"><span class="label">Đến ngày</span><input v-model="filters.date_to" class="input" type="date" /></label>
    </div>
    <div class="mt-3"><button class="btn" type="button" @click="reset">Xóa bộ lọc</button></div>
  </section>

  <section class="card">
    <div v-if="loading && !list.data.length" class="space-y-2 p-5"><div v-for="n in 6" :key="n" class="h-8 animate-pulse rounded bg-surface-muted"></div></div>
    <EmptyState v-else-if="!list.data.length" icon="scroll-text" title="Không có dòng nhật ký nào" text="Thử bớt điều kiện lọc." />
    <div v-else class="table-wrap" :class="{ 'opacity-60': loading }">
      <table class="data-table">
        <caption class="sr-only">Nhật ký hệ thống</caption>
        <thead><tr><th scope="col">Thời gian</th><th scope="col">Thao tác</th><th scope="col">Người dùng</th><th scope="col">Đối tượng</th><th scope="col">Nội dung</th></tr></thead>
        <tbody>
          <tr v-for="row in list.data" :key="row.name" class="is-clickable" tabindex="0" @click="openEntry(row)" @keydown.enter="openEntry(row)">
            <td class="whitespace-nowrap text-sm">{{ formatDateTime(row.timestamp) }}</td>
            <td><span class="badge badge-muted">{{ row.activity_type }}</span></td>
            <td class="text-sm">{{ row.user }}</td>
            <td class="text-sm">{{ row.reference_doctype }}<span v-if="row.reference_name" class="block text-xs text-ink-muted">{{ row.reference_name }}</span></td>
            <td class="max-w-md truncate text-sm text-ink-soft" :title="row.description">{{ row.description }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="list.searched_from" class="m-0 border-t border-line px-4 py-2 text-sm text-ink-muted" role="status">Tìm trong nhật ký từ {{ formatDate(list.searched_from) }} trở lại đây. Chọn "Từ ngày" để tìm xa hơn.</p>
    <PaginationBar v-if="list.total" :page="list.page" :page-size="list.page_size" :total="list.total" :capped="Boolean(list.total_capped)" @change="load" />
  </section>

  <Drawer :open="Boolean(entry)" :title="entry ? `Nhật ký ${entry.name}` : ''" width="560px" @close="entry = null">
    <dl v-if="entry" class="m-0 space-y-3 text-sm">
      <div><dt class="text-ink-muted">Thời gian</dt><dd class="m-0 font-medium">{{ formatDateTime(entry.timestamp) }}</dd></div>
      <div><dt class="text-ink-muted">Thao tác</dt><dd class="m-0 font-medium">{{ entry.activity_type }}</dd></div>
      <div><dt class="text-ink-muted">Người dùng</dt><dd class="m-0 font-medium">{{ entry.user }} <span class="text-ink-muted">{{ entry.ip_address }}</span></dd></div>
      <div><dt class="text-ink-muted">Đối tượng</dt><dd class="m-0 font-medium">{{ entry.reference_doctype }} {{ entry.reference_name }}</dd></div>
      <div><dt class="text-ink-muted">Nội dung</dt><dd class="m-0 whitespace-pre-wrap">{{ entry.description }}</dd></div>
      <div v-if="entry.data_json"><dt class="text-ink-muted">Dữ liệu kèm theo</dt><dd class="m-0"><pre class="m-0 max-h-80 overflow-auto rounded-md bg-surface-muted p-3 text-xs">{{ prettyJson(entry.data_json) }}</pre></dd></div>
    </dl>
  </Drawer>

  <Drawer :open="cleaning" title="Dọn dẹp nhật ký" width="560px" @close="cleaning = false">
    <div class="space-y-4">
      <p class="m-0 text-sm text-ink-soft">Xóa các dòng nhật ký cũ để giảm dung lượng. Luôn xem trước số dòng sẽ bị xóa; không dọn được nhật ký của 7 ngày gần nhất; việc dọn dẹp tự ghi lại vào nhật ký.</p>
      <p v-if="purge.error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ purge.error }}</p>
      <label class="block text-sm"><span class="label">Xóa các dòng trước ngày</span><input v-model="purge.before" class="input" type="date" :max="maxDate" @change="purge.preview = null" /></label>
      <fieldset class="space-y-1">
        <legend class="label">Chỉ các loại thao tác (không chọn: tất cả)</legend>
        <label v-for="t in options.activity_types" :key="t" class="mr-4 inline-flex cursor-pointer items-center gap-2 text-sm">
          <input type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" :checked="purge.types.includes(t)" @change="toggleType(t)" /> {{ t }}
        </label>
      </fieldset>
      <button class="btn" type="button" :disabled="!purge.before" @click="preview"><Icon name="search" :size="16" /> Xem trước</button>
      <section v-if="purge.preview" class="card px-4 py-3" aria-live="polite">
        <p class="m-0 text-sm">Sẽ xóa <strong>{{ formatNumber(purge.preview.total) }}</strong> dòng<template v-if="purge.preview.total"> (từ {{ formatDateTime(purge.preview.oldest) }} đến {{ formatDateTime(purge.preview.newest) }})</template>.</p>
        <ul v-if="purge.preview.by_type.length" class="mb-0 mt-2 list-none space-y-1 p-0 text-sm text-ink-soft"><li v-for="t in purge.preview.by_type" :key="t.activity_type">{{ t.activity_type }}: {{ formatNumber(t.count) }}</li></ul>
        <label v-if="purge.preview.total" class="mt-3 block text-sm"><span class="label">Gõ lại số dòng ({{ purge.preview.total }}) để xác nhận</span><input v-model="purge.typed" class="input" type="text" inputmode="numeric" autocomplete="off" /></label>
      </section>
    </div>
    <template #footer>
      <button class="btn" type="button" @click="cleaning = false">Hủy</button>
      <button class="btn btn-danger" type="button" :disabled="!canPurge" @click="runPurge"><Icon :name="purge.busy ? 'loader' : 'trash-2'" :size="16" :spin="purge.busy" /> Xóa</button>
    </template>
  </Drawer>
</template>
