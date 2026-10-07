<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import FormRenderer from "../components/FormRenderer.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { missingRequired } from "../lib/doctype.js";
import { toast } from "../lib/toast.js";

// A single DocType (settings) edited as one form: no list, the record is named after the DocType.
const props = defineProps({ meta: { type: Object, required: true } });

const record = reactive({});
const original = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const fieldErrors = reactive({});

const canWrite = computed(() => props.meta.permissions.write);
const dirty = computed(() => JSON.stringify(record) !== original.value);

function assign(values) {
  for (const key of Object.keys(record)) delete record[key];
  Object.assign(record, values);
  original.value = JSON.stringify(record);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    assign({ ...(await api.get(props.meta.doctype, props.meta.doctype)) });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

async function save() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
  const missing = missingRequired(props.meta, record);
  for (const item of missing) fieldErrors[item.fieldname] = `Vui lòng nhập ${item.label.toLowerCase()}`;
  if (missing.length) return (error.value = "Còn trường bắt buộc chưa được nhập.");
  saving.value = true;
  error.value = "";
  try {
    assign({ ...(await api.save(props.meta.doctype, { ...record }, props.meta.doctype)) });
    toast("Đã lưu thiết lập");
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <PageHeader :title="meta.label">
    <button v-if="canWrite" class="btn btn-primary" type="button" :disabled="saving || loading || !dirty" @click="save">
      <Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> Lưu thiết lập
    </button>
  </PageHeader>
  <div v-if="loading" class="flex items-center gap-2 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
  <section v-else class="card max-w-3xl p-5">
    <p v-if="error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
    <FormRenderer :meta="meta" :record="record" :errors="fieldErrors" :editing="true" :read-only="!canWrite" />
    <p v-if="!canWrite" class="mt-4 text-sm text-ink-muted">Bạn chỉ có quyền xem thiết lập này.</p>
  </section>
</template>
