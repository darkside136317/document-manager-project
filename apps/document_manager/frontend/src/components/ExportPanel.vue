<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { api } from "../lib/api.js";
import { allFields, countsRows, exportedLevels, fieldsPayload, isBusy, toggled, watchJob } from "../lib/exchange.js";
import { formatNumber } from "../lib/format.js";
import { cleanFilters, initialFilters } from "../lib/reports.js";
import FieldPicker from "./FieldPicker.vue";
import FilterForm from "./FilterForm.vue";
import Icon from "./Icon.vue";
import JobCard from "./JobCard.vue";

// Search the archive, see how many records that is, choose the fields, and export them as one XML file (in the background).
const props = defineProps({ caps: { type: Object, required: true } });
const emit = defineEmits(["finished"]);

const level = ref("Archival File");
const withChildren = ref(false);
const filters = ref({});
const preview = ref(null);
const choice = ref(allFields(props.caps.levels));
const job = ref(null);
const busy = ref(false);
const error = ref("");
let watcher = null;

const spec = computed(() => props.caps.levels.find((l) => l.doctype === level.value));
const shown = computed(() => props.caps.levels.filter((l) => exportedLevels(level.value, withChildren.value).includes(l.doctype)));
const rows = computed(() => (preview.value ? countsRows(props.caps.levels, preview.value.counts, preview.value.ancestors).filter((r) => r.count || r.ancestors) : []));
const running = computed(() => isBusy(job.value));

function pickLevel(doctype) {
  level.value = doctype;
  filters.value = initialFilters(spec.value.filters);
  preview.value = null;
  error.value = "";
}
pickLevel(level.value);

async function check() {
  busy.value = true;
  error.value = "";
  try {
    preview.value = await api.exchange.previewExport(level.value, cleanFilters(filters.value), withChildren.value);
  } catch (e) {
    error.value = e.message;
    preview.value = null;
  } finally {
    busy.value = false;
  }
}

async function start() {
  busy.value = true;
  error.value = "";
  try {
    job.value = await api.exchange.startExport(level.value, cleanFilters(filters.value), fieldsPayload(choice.value, shown.value.map((l) => l.doctype)), withChildren.value);
    follow(job.value.name);
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

function follow(name) {
  watcher?.stop();
  watcher = watchJob(name, { fetch: api.exchange.job, onUpdate: (next) => { job.value = next; } });
  watcher.done.then((last) => last && emit("finished", last)).catch((e) => { error.value = e.message; });
}

async function cancel(target) {
  try {
    await api.exchange.cancel(target.name);
  } catch (e) {
    error.value = e.message;
  }
}

const toggle = (lvl, name) => { choice.value = toggled(choice.value, lvl, name); };
const everything = (lvl) => { choice.value = { ...choice.value, [lvl.doctype]: new Set(lvl.fields.map((f) => f.fieldname)) }; };
const keysOnly = (lvl) => { choice.value = { ...choice.value, [lvl.doctype]: new Set(lvl.fields.filter((f) => f.key).map((f) => f.fieldname)) }; };
onBeforeUnmount(() => watcher?.stop());
</script>

<template>
  <div class="space-y-5">
    <section class="card px-5 py-4">
      <h2 class="mb-3 mt-0 text-base font-semibold">1. Chọn dữ liệu cần xuất</h2>
      <div class="mb-4 flex flex-wrap gap-2" role="radiogroup" aria-label="Cấp dữ liệu">
        <button
          v-for="l in caps.levels"
          :key="l.doctype"
          type="button"
          role="radio"
          :aria-checked="level === l.doctype"
          class="btn"
          :class="{ 'btn-primary': level === l.doctype }"
          @click="pickLevel(l.doctype)"
        >{{ l.label }}</button>
      </div>
      <FilterForm v-model="filters" :filters="spec.filters" :busy="busy" submit-label="Xem trước số lượng" @submit="check" @reset="pickLevel(level)">
        <template #actions>
          <label class="ml-2 flex cursor-pointer items-center gap-2 text-sm">
            <input v-model="withChildren" type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" @change="preview = null" />
            Kèm cả dữ liệu cấp dưới
          </label>
        </template>
      </FilterForm>
    </section>

    <p v-if="error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

    <section v-if="preview" class="card px-5 py-4">
      <h2 class="mb-3 mt-0 text-base font-semibold">2. Kết quả tìm kiếm</h2>
      <div class="table-wrap">
        <table class="data-table">
          <caption class="sr-only">Số bản ghi sẽ xuất</caption>
          <thead><tr><th scope="col">Cấp</th><th scope="col" class="text-right">Bản ghi</th><th scope="col" class="text-right">Cấp trên (chỉ khóa)</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.doctype"><td class="font-medium">{{ row.label }}</td><td class="text-right tabular-nums">{{ formatNumber(row.count) }}</td><td class="text-right tabular-nums text-ink-muted">{{ row.ancestors ? formatNumber(row.ancestors) : "" }}</td></tr>
          </tbody>
          <tfoot><tr class="font-semibold"><td>Tổng</td><td colspan="2" class="text-right tabular-nums">{{ formatNumber(preview.total) }} / tối đa {{ formatNumber(preview.limit) }}</td></tr></tfoot>
        </table>
      </div>
      <p v-if="preview.too_many" class="mb-0 mt-3 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning" role="alert">Vượt giới hạn {{ formatNumber(preview.limit) }} bản ghi một tệp. Hãy thu hẹp tiêu chí (theo phông, mục lục) rồi xuất từng phần.</p>
      <p v-else-if="!preview.counts[level]" class="mb-0 mt-3 text-sm text-ink-muted">Không có bản ghi nào khớp tiêu chí.</p>
    </section>

    <section v-if="preview && preview.counts[level] && !preview.too_many" class="card px-5 py-4">
      <h2 class="mb-1 mt-0 text-base font-semibold">3. Chọn các trường đưa vào tệp</h2>
      <p class="mb-4 mt-0 text-sm text-ink-muted">Mã (số) và tiêu đề của mỗi bản ghi luôn có trong tệp để nhận ra bản ghi khi nhập lại. Nội dung văn bản trích xuất và tệp đính kèm không nằm trong tệp XML.</p>
      <div class="space-y-4">
        <FieldPicker v-for="l in shown" :key="l.doctype" :level="l" :chosen="choice[l.doctype]" @toggle="toggle" @all="everything" @none="keysOnly" />
      </div>
      <div class="mt-5 flex flex-wrap items-center gap-3">
        <button class="btn btn-primary" type="button" :disabled="busy || running" @click="start">
          <Icon :name="busy || running ? 'loader' : 'file-down'" :size="16" :spin="busy || running" /> Xuất XML
        </button>
        <a class="text-sm" href="/api/method/document_manager.document_manager.api.exchange.download_schema">Tải lược đồ XSD</a>
      </div>
    </section>

    <JobCard v-if="job" :job="job" :levels="caps.levels" @cancel="cancel" />
  </div>
</template>
