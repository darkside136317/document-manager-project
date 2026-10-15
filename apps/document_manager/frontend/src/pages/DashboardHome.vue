<script setup>
import { computed, onMounted, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { boot } from "../lib/boot.js";
import { formatDateTime, formatNumber } from "../lib/format.js";

const summary = ref(null);
const error = ref("");
const loading = ref(true);

onMounted(async () => {
  try {
    summary.value = await api.summary();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
});

const cards = computed(() => {
  const s = summary.value;
  if (!s) return [];
  return [
    { label: "Phông lưu trữ", value: s.fonds, icon: "library", to: "/danh-muc/phong-luu-tru", tone: "primary" },
    { label: "Hồ sơ", value: s.archival_files, icon: "folder", to: "/bien-muc", tone: "info" },
    { label: "Văn bản, tài liệu", value: s.documents, icon: "file-text", to: "/tim-kiem?tab=van-ban", tone: "success" },
    { label: "Độc giả", value: s.readers, icon: "users", href: "/readers", tone: "info" },
    { label: "Đã lập chỉ mục tìm kiếm", value: s.documents ? `${s.index_percent}%` : "—", icon: "database", to: "/tim-kiem?tab=van-ban",
      tone: s.index_percent >= 90 || !s.documents ? "success" : "warning", hint: s.documents ? `${formatNumber(s.indexed_documents)} / ${formatNumber(s.documents)} văn bản` : "Chưa có văn bản" },
    { label: "Phiếu chờ duyệt", value: s.pending_usage + s.pending_copy, icon: "clipboard-list", href: "/usage_requests",
      tone: s.pending_usage + s.pending_copy ? "warning" : "success", hint: `${s.pending_usage} sử dụng · ${s.pending_copy} sao chụp` },
    { label: "Lỗi toàn vẹn dữ liệu", value: s.integrity_errors, icon: "shield-check", href: "/integrity_checks", tone: s.integrity_errors ? "danger" : "success" },
  ];
});
const toneClass = { primary: "bg-primary-soft text-primary", info: "bg-info-soft text-info", success: "bg-success-soft text-success", warning: "bg-warning-soft text-warning", danger: "bg-danger-soft text-danger" };
</script>

<template>
  <PageHeader title="Tổng quan" :subtitle="`Xin chào ${boot.user.full_name}. Đây là tình hình hệ thống lưu trữ hôm nay.`" />

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
  <div v-if="!boot.org_configured && boot.admin.some((entry) => entry.slug === 'thong-tin-don-vi')" class="mb-4 rounded-md border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-ink" role="status">
    Trang công khai đang dùng tên đơn vị mặc định. <RouterLink class="font-semibold" to="/quan-tri/thong-tin-don-vi">Cập nhật thông tin đơn vị</RouterLink> để hiển thị tên, địa chỉ và liên hệ của khách hàng.
  </div>

  <div class="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
    <template v-if="loading">
      <div v-for="n in 4" :key="n" class="card h-[104px] animate-pulse bg-surface-muted"></div>
    </template>
    <component :is="card.to ? 'RouterLink' : 'a'" v-for="card in cards" :key="card.label" v-bind="card.to ? { to: card.to } : { href: card.href }" class="card flex min-w-0 flex-col items-start gap-2 p-3 text-ink no-underline transition-shadow hover:shadow-pop sm:flex-row sm:items-center sm:gap-4 sm:p-4">
      <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg sm:h-11 sm:w-11" :class="toneClass[card.tone]"><Icon :name="card.icon" :size="22" /></span>
      <span class="min-w-0">
        <span class="block text-xl font-semibold leading-tight sm:text-2xl">{{ typeof card.value === 'number' ? formatNumber(card.value) : card.value }}</span>
        <span class="block text-xs leading-snug text-ink-muted sm:truncate sm:text-sm">{{ card.label }}</span>
        <span v-if="card.hint" class="hidden truncate text-xs text-ink-subtle sm:block">{{ card.hint }}</span>
      </span>
    </component>
  </div>

  <div class="mt-6 grid gap-6 lg:grid-cols-3">
    <section class="card lg:col-span-2">
      <header class="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 class="m-0 text-sm font-semibold">Văn bản cập nhật gần đây</h2>
        <RouterLink class="text-sm" to="/tim-kiem?tab=van-ban">Xem tất cả</RouterLink>
      </header>
      <EmptyState v-if="summary && !summary.recent_documents.length" icon="file-text" title="Chưa có văn bản" text="Văn bản mới tạo sẽ hiện ở đây." />
      <ul v-else class="m-0 list-none divide-y divide-line p-0">
        <li v-for="doc in summary?.recent_documents || []" :key="doc.name" class="flex items-center gap-3 px-5 py-3">
          <Icon name="file-text" class="shrink-0 text-ink-muted" />
          <div class="min-w-0 flex-1">
            <RouterLink class="block truncate text-sm font-medium" :to="`/van-ban/${encodeURIComponent(doc.name)}`">{{ doc.document_title || doc.name }}</RouterLink>
            <span class="text-xs text-ink-muted">{{ doc.name }} · {{ doc.file_type || "—" }} · {{ formatDateTime(doc.modified) }}</span>
          </div>
          <span class="badge" :class="doc.search_index_status === 'Đã index' ? 'badge-success' : doc.search_index_status === 'Lỗi' ? 'badge-danger' : 'badge-muted'">
            {{ doc.search_index_status }}
          </span>
        </li>
      </ul>
    </section>

    <section class="card">
      <header class="border-b border-line px-5 py-3"><h2 class="m-0 text-sm font-semibold">Danh mục dùng chung</h2></header>
      <ul class="m-0 list-none p-2">
        <li v-for="master in boot.masters" :key="master.slug">
          <RouterLink class="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-ink no-underline hover:bg-surface-muted" :to="`/danh-muc/${master.slug}`">
            <Icon :name="master.icon" :size="17" class="text-ink-muted" /> {{ master.label }}
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>
