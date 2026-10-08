<script setup>
import { onMounted, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { boot } from "../lib/boot.js";

// The catalogue of reports the user may run, by group.
const groups = ref([]);
const error = ref("");
const loading = ref(true);
const inventory = boot.inventory?.[0] || null;

onMounted(async () => {
  try {
    groups.value = await api.reports.list();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <PageHeader title="Thống kê, báo cáo" subtitle="Chọn một báo cáo, đặt điều kiện lọc rồi xem, xuất Excel, CSV hoặc in có đầu đơn vị.">
    <RouterLink v-if="inventory" class="btn" :to="`/${inventory.slug}`"><Icon :name="inventory.icon" :size="16" /> {{ inventory.label }}</RouterLink>
  </PageHeader>

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
  <div v-if="loading" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><div v-for="n in 6" :key="n" class="card h-28 animate-pulse bg-surface-muted"></div></div>
  <EmptyState v-else-if="!groups.length" icon="chart-bar" title="Chưa có báo cáo nào dành cho bạn" text="Tài khoản của bạn chưa có quyền xem dữ liệu của các báo cáo." />

  <section v-for="group in groups" :key="group.group" class="mb-8">
    <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">{{ group.group }}</h2>
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <RouterLink
        v-for="report in group.reports"
        :key="report.slug"
        :to="`/bao-cao/${report.slug}`"
        class="card flex gap-4 p-4 text-ink no-underline transition-shadow hover:shadow-pop"
      >
        <span class="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary"><Icon :name="report.icon" :size="22" /></span>
        <span class="min-w-0">
          <span class="block font-semibold leading-snug">{{ report.title }}</span>
          <span class="mt-1 block text-sm text-ink-muted">{{ report.description }}</span>
        </span>
      </RouterLink>
    </div>
  </section>
</template>
