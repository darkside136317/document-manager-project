<script setup>
import { computed } from "vue";
import { downloadUrl, jobHeadline, resultRows } from "../lib/exchange.js";
import { formatDateTime, formatNumber } from "../lib/format.js";
import Icon from "./Icon.vue";
import StatusBadge from "./StatusBadge.vue";

// How one export or import went (or is going): status, progress, the counters per level and the log of what failed.
const props = defineProps({
  job: { type: Object, required: true },
  levels: { type: Array, default: () => [] },
});
const emit = defineEmits(["cancel"]);

const rows = computed(() => resultRows(props.job, props.levels));
const isImport = computed(() => props.job.direction === "Nhập");
const columns = computed(() => (isImport.value
  ? [["created", "Thêm mới"], ["updated", "Cập nhật"], ["unchanged", "Không đổi"], ["exists", "Đã có"], ["refs", "Tham chiếu"], ["failed", "Lỗi"]]
  : [["exported", "Đã xuất"], ["ancestors", "Cấp trên (tham chiếu)"]]));
const severityClass = { Lỗi: "badge-danger", "Cảnh báo": "badge-warning", "Thông tin": "badge-info" };
</script>

<template>
  <section class="card" :aria-live="job.busy ? 'polite' : 'off'" :aria-label="`${job.direction} XML ${job.name}`">
    <header class="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
      <StatusBadge :value="job.status" />
      <span v-if="job.dry_run && isImport" class="badge badge-info">Chạy thử</span>
      <h3 class="m-0 min-w-0 flex-1 truncate text-sm font-semibold">{{ job.file_name || job.name }}</h3>
      <span class="text-xs text-ink-muted">{{ job.name }} · {{ formatDateTime(job.creation) }}</span>
    </header>

    <div class="space-y-4 px-5 py-4">
      <p class="m-0 text-sm" :class="job.status === 'Thất bại' ? 'text-danger' : 'text-ink-soft'">
        <Icon v-if="job.busy" name="loader" :size="14" spin class="mr-1 inline" />{{ jobHeadline(job) }}
      </p>

      <div v-if="job.busy" class="space-y-1">
        <div class="h-2 overflow-hidden rounded-full bg-surface-muted" role="progressbar" :aria-valuenow="job.percent" aria-valuemin="0" aria-valuemax="100">
          <div class="h-2 rounded-full bg-primary transition-all" :style="{ width: `${job.percent}%` }"></div>
        </div>
        <p class="m-0 text-xs text-ink-muted">{{ formatNumber(job.processed) }} / {{ formatNumber(job.total) }} bản ghi ({{ job.percent }}%)</p>
      </div>

      <dl v-if="!job.busy && job.finished_on" class="m-0 flex flex-wrap gap-x-8 gap-y-1 text-sm">
        <div v-if="isImport"><dt class="inline text-ink-muted">Thêm mới: </dt><dd class="inline font-semibold">{{ formatNumber(job.created) }}</dd></div>
        <div v-if="isImport"><dt class="inline text-ink-muted">Cập nhật: </dt><dd class="inline font-semibold">{{ formatNumber(job.updated) }}</dd></div>
        <div v-if="isImport"><dt class="inline text-ink-muted">Bỏ qua: </dt><dd class="inline font-semibold">{{ formatNumber(job.skipped) }}</dd></div>
        <div v-if="isImport"><dt class="inline text-ink-muted">Lỗi: </dt><dd class="inline font-semibold" :class="job.failed ? 'text-danger' : ''">{{ formatNumber(job.failed) }}</dd></div>
        <div v-if="job.file_size_kb"><dt class="inline text-ink-muted">Dung lượng: </dt><dd class="inline font-semibold">{{ formatNumber(Math.round(job.file_size_kb)) }} KB</dd></div>
        <div v-if="job.checksum" class="min-w-0"><dt class="inline text-ink-muted">SHA-256: </dt><dd class="inline break-all font-mono text-xs">{{ job.checksum }}</dd></div>
      </dl>

      <div v-if="rows.length" class="table-wrap">
        <table class="data-table">
          <caption class="sr-only">Kết quả theo cấp</caption>
          <thead><tr><th scope="col">Cấp</th><th v-for="[key, label] in columns" :key="key" scope="col" class="text-right">{{ label }}</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.doctype">
              <td class="font-medium">{{ row.label }}</td>
              <td v-for="[key] in columns" :key="key" class="text-right tabular-nums" :class="key === 'failed' && row[key] ? 'font-semibold text-danger' : ''">{{ formatNumber(row[key] || 0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="job.rows?.length">
        <h4 class="mb-2 mt-0 text-sm font-semibold">Nhật ký ({{ job.rows_total }}{{ job.rows_total > job.rows.length ? `, hiện ${job.rows.length}` : "" }})</h4>
        <div class="table-wrap max-h-80 overflow-y-auto">
          <table class="data-table">
            <thead><tr><th scope="col">Mức</th><th scope="col">Cấp</th><th scope="col">Vị trí</th><th scope="col">Nội dung</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in job.rows" :key="index">
                <td><span class="badge" :class="severityClass[row.severity] || 'badge-muted'">{{ row.severity }}</span></td>
                <td>{{ row.level }}</td>
                <td class="max-w-xs break-words text-xs text-ink-soft">{{ row.path }}</td>
                <td class="break-words text-sm">{{ row.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <footer v-if="job.busy || job.has_result || $slots.default" class="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3">
      <a v-if="job.has_result" class="btn btn-primary" :href="downloadUrl(job.name)"><Icon name="download" :size="16" /> Tải tệp XML</a>
      <button v-if="job.busy" class="btn" type="button" @click="emit('cancel', job)"><Icon name="ban" :size="16" /> Dừng</button>
      <slot />
    </footer>
  </section>
</template>
