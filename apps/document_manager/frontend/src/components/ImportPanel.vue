<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { api } from "../lib/api.js";
import { allFields, countsRows, fieldsPayload, isBusy, toggled, watchJob } from "../lib/exchange.js";
import { formatDateTime, formatNumber } from "../lib/format.js";
import { extensionOf, formatSize, uploadFile } from "../lib/upload.js";
import ConfirmDialog from "./ConfirmDialog.vue";
import FieldPicker from "./FieldPicker.vue";
import Icon from "./Icon.vue";
import JobCard from "./JobCard.vue";

// Upload an XML file, see what it contains, choose how and which fields to import, rehearse it (dry run) and import.
const props = defineProps({ caps: { type: Object, required: true } });
const emit = defineEmits(["finished"]);

const dragging = ref(false);
const input = ref(null);
const stage = ref("");
const progress = ref(0);
const error = ref("");
const problems = ref([]);
const upload = ref(null); // the analysed job
const choice = ref({});
const mode = ref(props.caps.modes[0]);
const createMasters = ref(false);
const run = ref(null);
const confirm = ref(false);
let watcher = null;

const analysis = computed(() => upload.value?.analysis || null);
const levels = computed(() => props.caps.levels.filter((l) => (analysis.value?.counts[l.doctype]?.nodes || 0) > 0));
const rows = computed(() => (analysis.value ? countsRows(props.caps.levels, Object.fromEntries(Object.entries(analysis.value.counts).map(([k, v]) => [k, v.nodes])), Object.fromEntries(Object.entries(analysis.value.counts).map(([k, v]) => [k, v.ref]))).filter((r) => r.count) : []));
const running = computed(() => isBusy(run.value));
const busy = computed(() => Boolean(stage.value) || running.value);
const rehearsed = computed(() => run.value?.dry_run && !run.value.busy && run.value.status !== "Thất bại");

function reset() {
  watcher?.stop();
  stage.value = "";
  progress.value = 0;
  error.value = "";
  problems.value = [];
  upload.value = null;
  run.value = null;
  choice.value = {};
}

async function choose(file) {
  reset();
  if (!file) return;
  if (extensionOf(file.name) !== "xml") return (error.value = "Chỉ nhận tệp có đuôi .xml");
  if (file.size === 0) return (error.value = "Tệp rỗng");
  if (file.size > props.caps.max_mb * 1024 * 1024) return (error.value = `Tệp lớn hơn ${props.caps.max_mb} MB (${formatSize(file.size)})`);
  try {
    stage.value = "Đang tải lên...";
    const stored = await uploadFile(file, { onProgress: (p) => { progress.value = p; } });
    stage.value = "Đang đọc và kiểm tra tệp...";
    const result = await api.exchange.analyze(stored.file_url);
    if (!result.valid) {
      problems.value = result.errors;
      return;
    }
    upload.value = result.job;
    choice.value = allFields(props.caps.levels, result.job.analysis.fields);
  } catch (e) {
    error.value = e.message;
  } finally {
    stage.value = "";
  }
}

const onPick = (event) => { choose(event.target.files[0]); event.target.value = ""; };
const onDrop = (event) => { dragging.value = false; choose(event.dataTransfer.files[0]); };

async function start(dry) {
  confirm.value = false;
  error.value = "";
  stage.value = dry ? "Đang gửi yêu cầu chạy thử..." : "Đang gửi yêu cầu nhập...";
  try {
    run.value = await api.exchange.startImport(upload.value.name, {
      mode: mode.value, fields: fieldsPayload(choice.value, levels.value.map((l) => l.doctype)),
      dry_run: dry ? 1 : 0, create_masters: createMasters.value ? 1 : 0,
    });
    watcher?.stop();
    watcher = watchJob(run.value.name, { fetch: api.exchange.job, onUpdate: (next) => { run.value = next; } });
    watcher.done.then((last) => last && emit("finished", last)).catch((e) => { error.value = e.message; });
  } catch (e) {
    error.value = e.message;
  } finally {
    stage.value = "";
  }
}

async function cancel(job) {
  try {
    await api.exchange.cancel(job.name);
  } catch (e) {
    error.value = e.message;
  }
}

const toggle = (lvl, name) => { choice.value = toggled(choice.value, lvl, name); };
const everything = (lvl) => { choice.value = { ...choice.value, [lvl.doctype]: new Set(Object.keys(analysis.value.fields[lvl.doctype] || {})) }; };
const keysOnly = (lvl) => { choice.value = { ...choice.value, [lvl.doctype]: new Set(lvl.fields.filter((f) => f.key && f.fieldname in (analysis.value.fields[lvl.doctype] || {})).map((f) => f.fieldname)) }; };
onBeforeUnmount(() => watcher?.stop());
</script>

<template>
  <div class="space-y-5">
    <section class="card px-5 py-4">
      <h2 class="mb-3 mt-0 text-base font-semibold">1. Chọn tệp XML</h2>
      <div
        class="grid place-items-center rounded-lg border-2 border-dashed px-4 py-8 text-center"
        :class="dragging ? 'border-primary bg-primary-soft' : 'border-line'"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <Icon name="file-code" :size="28" class="text-ink-subtle" />
        <p class="mb-3 mt-2 text-sm text-ink-soft">Kéo tệp XML vào đây hoặc chọn từ máy (tối đa {{ caps.max_mb }} MB). Tệp phải theo <a href="/api/method/document_manager.document_manager.api.exchange.download_schema">lược đồ XSD</a> của hệ thống.</p>
        <input ref="input" class="sr-only" type="file" accept=".xml,application/xml,text/xml" aria-label="Chọn tệp XML" @change="onPick" />
        <button class="btn" type="button" :disabled="busy" @click="input.click()"><Icon name="upload" :size="16" /> Chọn tệp</button>
      </div>
      <div v-if="stage" class="mt-3 flex items-center gap-2 text-sm text-ink-soft" role="status">
        <Icon name="loader" :size="14" spin /> {{ stage }} <span v-if="progress && progress < 100">{{ progress }}%</span>
      </div>
    </section>

    <p v-if="error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
    <section v-if="problems.length" class="card border-danger px-5 py-4" role="alert">
      <h2 class="mb-2 mt-0 text-base font-semibold text-danger">Tệp không đúng định dạng của hệ thống</h2>
      <ul class="m-0 list-disc space-y-1 pl-5 text-sm"><li v-for="(p, i) in problems" :key="i" class="break-words">{{ p }}</li></ul>
    </section>

    <template v-if="upload && analysis">
      <section class="card px-5 py-4">
        <h2 class="mb-3 mt-0 text-base font-semibold">2. Nội dung tệp</h2>
        <dl class="m-0 mb-4 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          <div><dt class="inline text-ink-muted">Tệp: </dt><dd class="inline font-medium">{{ upload.file_name }} ({{ formatNumber(Math.round(upload.file_size_kb)) }} KB)</dd></div>
          <div><dt class="inline text-ink-muted">Phiên bản lược đồ: </dt><dd class="inline font-medium">{{ analysis.attributes.version }}</dd></div>
          <div v-if="analysis.attributes.source"><dt class="inline text-ink-muted">Nguồn: </dt><dd class="inline font-medium">{{ analysis.attributes.source }}</dd></div>
          <div v-if="analysis.attributes.exported_at"><dt class="inline text-ink-muted">Xuất lúc: </dt><dd class="inline font-medium">{{ formatDateTime(analysis.attributes.exported_at.replace('T', ' ')) }}</dd></div>
        </dl>
        <div class="table-wrap">
          <table class="data-table">
            <caption class="sr-only">Số bản ghi trong tệp</caption>
            <thead><tr><th scope="col">Cấp</th><th scope="col" class="text-right">Bản ghi</th><th scope="col" class="text-right">Trong đó chỉ là tham chiếu</th></tr></thead>
            <tbody><tr v-for="row in rows" :key="row.doctype"><td class="font-medium">{{ row.label }}</td><td class="text-right tabular-nums">{{ formatNumber(row.count) }}</td><td class="text-right tabular-nums text-ink-muted">{{ row.ancestors ? formatNumber(row.ancestors) : "" }}</td></tr></tbody>
            <tfoot><tr class="font-semibold"><td>Tổng</td><td colspan="2" class="text-right tabular-nums">{{ formatNumber(analysis.total) }}</td></tr></tfoot>
          </table>
        </div>
        <ul v-if="analysis.warnings.length" class="mb-0 mt-3 list-disc space-y-1 rounded-md bg-warning-soft py-2 pl-7 pr-3 text-sm text-warning" role="status">
          <li v-for="(w, i) in analysis.warnings" :key="i">{{ w }}</li>
        </ul>
      </section>

      <section class="card px-5 py-4">
        <h2 class="mb-3 mt-0 text-base font-semibold">3. Cách nhập</h2>
        <div class="space-y-2" role="radiogroup" aria-label="Cách nhập">
          <label v-for="option in caps.modes" :key="option" class="flex cursor-pointer items-start gap-2 text-sm">
            <input v-model="mode" type="radio" name="import-mode" :value="option" class="mt-0.5 accent-[var(--dm-primary)]" />
            <span><strong>{{ option }}</strong> —
              <template v-if="option === caps.modes[0]">bản ghi đã có (cùng mã hoặc tiêu đề trong cùng cấp cha) được giữ nguyên.</template>
              <template v-else>bản ghi đã có được cập nhật theo các trường đã chọn; bản ghi mới được thêm.</template>
            </span>
          </label>
        </div>
        <label class="mt-3 flex cursor-pointer items-start gap-2 text-sm">
          <input v-model="createMasters" type="checkbox" class="mt-0.5 h-4 w-4 accent-[var(--dm-primary)]" />
          <span><strong>Tạo danh mục còn thiếu</strong> ({{ caps.masters.join(", ") }}) khi tệp nhắc đến giá trị chưa có. Mức độ mật không bao giờ được tạo tự động.</span>
        </label>
      </section>

      <section class="card px-5 py-4">
        <h2 class="mb-1 mt-0 text-base font-semibold">4. Chọn các trường đưa vào cơ sở dữ liệu</h2>
        <p class="mb-4 mt-0 text-sm text-ink-muted">Chỉ các trường có trong tệp được liệt kê. Trường bắt buộc để tạo mới (tên, mã, cơ quan lưu trữ của phông…) luôn được dùng khi thêm bản ghi.</p>
        <div class="space-y-4">
          <FieldPicker v-for="l in levels" :key="l.doctype" :level="l" :chosen="choice[l.doctype] || new Set()" :found="analysis.fields[l.doctype]" @toggle="toggle" @all="everything" @none="keysOnly" />
        </div>
        <div class="mt-5 flex flex-wrap items-center gap-3">
          <button class="btn" type="button" :disabled="busy" @click="start(true)"><Icon name="play" :size="16" /> Chạy thử</button>
          <button class="btn btn-primary" type="button" :disabled="busy" @click="confirm = true"><Icon name="upload" :size="16" /> Nhập dữ liệu</button>
          <span v-if="rehearsed" class="text-sm text-success">Đã chạy thử xong: xem kết quả bên dưới rồi nhập thật.</span>
        </div>
      </section>
    </template>

    <JobCard v-if="run" :job="run" :levels="caps.levels" @cancel="cancel" />

    <ConfirmDialog
      :open="confirm"
      title="Nhập dữ liệu vào hệ thống?"
      :message="`Dữ liệu trong tệp sẽ được ${mode === caps.modes[0] ? 'thêm vào' : 'thêm vào và cập nhật'} cơ sở dữ liệu. Nên chạy thử trước. Thao tác ghi vào dữ liệu thật và được lưu trong nhật ký hệ thống.`"
      confirm-text="Nhập dữ liệu"
      @confirm="start(false)"
      @cancel="confirm = false"
    />
  </div>
</template>
