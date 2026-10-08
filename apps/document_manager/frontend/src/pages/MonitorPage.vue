<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { diskTone, indexTone, queueText, serviceTone } from "../lib/admin.js";
import { formatDateTime, formatNumber } from "../lib/format.js";
import { ageText, ageTone, formatBytes } from "../lib/preservation.js";

// The state of the whole system on one screen: services, the search index, background jobs, storage, backups, users and the log.
const data = ref(null);
const error = ref("");
const loading = ref(false);
let timer = null;

async function load() {
  loading.value = true;
  try {
    data.value = await api.monitor();
    error.value = "";
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
    clearTimeout(timer);
    timer = setTimeout(load, 30000);
  }
}
onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
const toneText = { success: "text-success", warning: "text-warning", danger: "text-danger", muted: "text-ink-muted" };
</script>

<template>
  <PageHeader title="Giám sát hệ thống" :subtitle="data ? `Site ${data.site} · cập nhật ${formatDateTime(data.checked_at)}` : 'Tình trạng vận hành của hệ thống.'">
    <button class="btn" type="button" :disabled="loading" @click="load"><Icon name="refresh-cw" :size="16" :spin="loading" /> Làm mới</button>
  </PageHeader>

  <EmptyState v-if="error" icon="alert-triangle" title="Không đọc được tình trạng hệ thống" :text="error" />
  <div v-else-if="!data" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><div v-for="n in 6" :key="n" class="card h-32 animate-pulse bg-surface-muted"></div></div>

  <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    <section class="card px-4 py-4" aria-label="Dịch vụ">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="server" :size="16" /> Dịch vụ</h2>
      <p v-for="(service, name) in data.services" :key="name" class="m-0 mb-2 text-sm">
        <span class="font-medium">{{ name === "mongodb" ? "MongoDB Atlas (GridFS)" : "Meilisearch" }}</span>:
        <span :class="toneText[serviceTone(service)]">{{ service.ok ? "Kết nối được" : "Không kết nối" }}</span>
        <span class="block text-xs text-ink-muted">{{ service.ok ? (name === "mongodb" ? `${formatNumber(service.files)} tệp` : `${formatNumber(service.documents)} văn bản trong chỉ mục`) : service.message }}</span>
      </p>
    </section>

    <section class="card px-4 py-4" aria-label="Chỉ mục tìm kiếm">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="database" :size="16" /> Chỉ mục tìm kiếm</h2>
      <p class="m-0 text-2xl font-semibold" :class="toneText[indexTone(data.documents)]">{{ data.documents.percent }}%</p>
      <p class="m-0 text-sm text-ink-soft">{{ formatNumber(data.documents.indexed) }} / {{ formatNumber(data.documents.total) }} văn bản đã lập chỉ mục</p>
      <p v-if="data.documents.errors" class="m-0 mt-1 text-sm text-danger">{{ formatNumber(data.documents.errors) }} văn bản lập chỉ mục lỗi</p>
    </section>

    <section class="card px-4 py-4" aria-label="Công việc nền">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="activity" :size="16" /> Công việc nền</h2>
      <p class="m-0 text-sm">Hàng đợi: {{ queueText(data.jobs.queues) }}</p>
      <p class="m-0 text-sm text-ink-soft">{{ data.jobs.workers === null ? "Không đọc được số tiến trình" : `${data.jobs.workers} tiến trình xử lý` }}</p>
      <p class="m-0 mt-1 text-sm" :class="data.jobs.errors_24h ? 'text-warning' : 'text-ink-soft'">{{ formatNumber(data.jobs.errors_24h) }} lỗi hệ thống trong 24 giờ · {{ formatNumber(data.jobs.failed_7d) }} tác vụ định kỳ lỗi trong 7 ngày</p>
    </section>

    <section class="card px-4 py-4" aria-label="Lưu trữ">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="hard-drive" :size="16" /> Lưu trữ</h2>
      <template v-if="data.storage.disk">
        <p class="m-0 text-2xl font-semibold" :class="toneText[diskTone(data.storage.disk)]">{{ data.storage.disk.used_percent }}% đã dùng</p>
        <p class="m-0 text-sm text-ink-soft">Còn {{ data.storage.disk.free_gb }} GB trên {{ data.storage.disk.total_gb }} GB</p>
      </template>
      <p class="m-0 mt-1 text-sm text-ink-soft">Tệp tài liệu: {{ formatNumber(Math.round(data.storage.private_files_mb)) }} MB · kho sao lưu tệp: {{ formatBytes(data.storage.backup_store.bytes) }}</p>
    </section>

    <section class="card px-4 py-4" aria-label="Sao lưu và kiểm tra">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="shield-check" :size="16" /> Sao lưu và kiểm tra</h2>
      <p class="m-0 text-sm">Sao lưu gần nhất: <strong :class="toneText[ageTone(data.backups.last?.age_days, 'Hàng tuần')]">{{ ageText(data.backups.last?.age_days) }}</strong></p>
      <p class="m-0 text-sm">Kiểm tra gần nhất:
        <template v-if="data.backups.last_check"><strong :class="data.backups.last_check.errors_found ? 'text-danger' : 'text-success'">{{ data.backups.last_check.errors_found ? `${data.backups.last_check.errors_found} lỗi` : "không có lỗi" }}</strong> ({{ formatDateTime(data.backups.last_check.completed_at) }})</template>
        <template v-else>chưa có</template>
      </p>
      <p class="m-0 mt-2 text-sm"><RouterLink to="/bao-quan/sao-luu">Sao lưu</RouterLink> · <RouterLink to="/bao-quan/kiem-tra">Kiểm tra toàn vẹn</RouterLink></p>
    </section>

    <section class="card px-4 py-4" aria-label="Người dùng và nhật ký">
      <h2 class="m-0 mb-3 flex items-center gap-2 text-sm font-semibold"><Icon name="users" :size="16" /> Người dùng và nhật ký</h2>
      <p class="m-0 text-sm">{{ formatNumber(data.users.staff) }} cán bộ đang hoạt động · {{ formatNumber(data.users.readers) }} độc giả</p>
      <p class="m-0 text-sm text-ink-soft">Nhật ký: {{ formatNumber(data.log.rows) }} dòng ({{ formatNumber(data.log.last_24h) }} trong 24 giờ qua)</p>
      <p class="m-0 mt-2 text-sm"><RouterLink to="/quan-tri/nguoi-dung">Người dùng</RouterLink> · <RouterLink to="/quan-tri/nhat-ky">Nhật ký</RouterLink></p>
    </section>
  </div>
</template>
