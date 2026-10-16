<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/api.js";
import { boot } from "../lib/boot.js";
import { pageTitle } from "../lib/page.js";

const route = useRoute();
const BASE = "document_manager.document_manager.api.ai_integration";
const job = ref(null);
const selected = reactive({});
const busy = ref(false);
const error = ref("");
const notice = ref("");
const canReview = computed(() => boot.user?.roles?.includes("Document Admin") ||
  boot.user?.capabilities?.includes("digitization.review"));
let timer;

async function load(poll = false) {
  busy.value = true; error.value = "";
  try {
    job.value = await call(`${BASE}.${poll ? "refresh" : "status"}`, { job_id: route.params.id }, { post: poll });
    for (const doc of job.value.documents || []) {
      if (!selected[doc.document_id]) selected[doc.document_id] = Object.fromEntries(Object.keys(doc.fields || {}).map((key) => [key, false]));
    }
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
async function review(doc) {
  busy.value = true; error.value = ""; notice.value = "";
  try {
    await call(`${BASE}.review`, { job_id: route.params.id, document_id: doc.document_id,
      approved_fields: Object.entries(selected[doc.document_id] || {}).filter(([, checked]) => checked).map(([key]) => key) }, { post: true });
    notice.value = `Đã duyệt ${doc.document_id}.`;
    await load();
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
const fieldLabel = (id) => job.value?.schema?.find((field) => field.field_id === id)?.label || id;
onMounted(() => { pageTitle.value = "Kết quả AI bóc tách"; load();
  timer = window.setInterval(() => { if (job.value && ["waiting", "processing"].includes(job.value.status)) load(); }, 15000);
});
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <PageHeader title="Kết quả AI bóc tách" :subtitle="`Job ${route.params.id}`">
    <button class="btn" type="button" :disabled="busy" @click="load(true)">Làm mới trạng thái AI</button>
  </PageHeader>
  <p v-if="error" class="rounded bg-danger-soft p-3 text-danger" role="alert">{{ error }}</p>
  <p v-if="notice" class="rounded bg-primary-soft p-3" role="status">{{ notice }}</p>
  <div v-if="job" class="space-y-4">
    <div class="card p-4"><p class="m-0">Trạng thái: <strong>{{ job.status }}</strong> · Khối tài liệu: {{ job.record_group }}</p><p v-if="job.error" class="text-danger">{{ job.error }}</p>
      <p class="mb-0 text-sm text-ink-muted">Kết quả được gắn với mã văn bản trong ERP. Chỉ các trường được chọn và xác nhận mới cập nhật dữ liệu.</p></div>
    <div v-for="doc in job.documents || []" :key="doc.document_id" class="card p-4">
      <div class="flex items-center justify-between gap-3"><h2 class="m-0 text-base font-semibold">{{ doc.document_id }} · {{ job.document_states?.[doc.document_id] === 'reviewed' ? '✓ Đã duyệt' : doc.status === 'done' ? '⚠ Chưa duyệt' : '⚠ Bóc tách lỗi' }}</h2><RouterLink :to="`/van-ban/${encodeURIComponent(doc.document_id)}`" class="btn no-underline">Xem văn bản</RouterLink></div>
      <p v-if="doc.error" class="text-danger">{{ doc.error }}</p>
      <div v-for="(answer, id) in doc.fields || {}" :key="id" class="flex items-start gap-3 border-b border-line py-2 text-sm">
        <input v-if="canReview && doc.status === 'done'" v-model="selected[doc.document_id][id]" type="checkbox" :aria-label="`Duyệt ${fieldLabel(id)}`" />
        <span class="w-48 shrink-0 font-medium">{{ fieldLabel(id) }}</span><span class="break-words">{{ answer.value ?? 'Chưa tìm thấy' }}</span>
      </div>
      <button v-if="canReview && doc.status === 'done' && job.document_states?.[doc.document_id] !== 'reviewed'" class="btn btn-primary mt-3" type="button" :disabled="busy" @click="review(doc)">Duyệt trường đã chọn</button>
    </div>
  </div>
</template>
