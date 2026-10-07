<script setup>
import { computed, reactive, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { blankRecord, missingRequired } from "../lib/doctype.js";
import { toast } from "../lib/toast.js";
import ConfirmDialog from "./ConfirmDialog.vue";
import { extrasFor } from "./extras.js";
import Drawer from "./Drawer.vue";
import FormRenderer from "./FormRenderer.vue";
import Icon from "./Icon.vue";

// Create / edit / delete one record of a registered DocType in a side drawer.
const props = defineProps({
  open: { type: Boolean, default: false },
  meta: { type: Object, required: true },
  name: { type: String, default: null }, // null = create
  defaults: { type: Object, default: () => ({}) },
  linkFilters: { type: Function, default: () => null },
});
const emit = defineEmits(["close", "saved", "deleted"]);

const record = reactive({});
const original = ref("");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const fieldErrors = reactive({});
const confirmDelete = reactive({ open: false, busy: false, error: "" });

const editing = computed(() => Boolean(props.name));
const extra = computed(() => extrasFor[props.meta.doctype] || null);
const canWrite = computed(() => (editing.value ? props.meta.permissions.write : props.meta.permissions.create));
const canDelete = computed(() => editing.value && props.meta.permissions.delete);
const title = computed(() => {
  if (!editing.value) return `Thêm mới — ${props.meta.label}`;
  return `${props.meta.label}: ${record[props.meta.title_field] || props.name}`;
});
const dirty = computed(() => JSON.stringify(record) !== original.value);

function assign(values) {
  for (const key of Object.keys(record)) delete record[key];
  Object.assign(record, values);
  original.value = JSON.stringify(record);
}
function resetMessages() {
  error.value = "";
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key];
}

// `quiet` re-reads the record without swapping the form for the spinner, so an extras panel that asked for
// the refresh (and may have a dialog open) is not torn down underneath itself.
async function load({ quiet = false } = {}) {
  resetMessages();
  if (!editing.value) {
    assign(blankRecord(props.meta, props.defaults));
    return;
  }
  if (!quiet) loading.value = true;
  try {
    assign({ ...(await api.get(props.meta.doctype, props.name)) });
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
watch(() => [props.open, props.name], ([open]) => { if (open) load(); }, { immediate: true });

function validate() {
  resetMessages();
  const missing = missingRequired(props.meta, record);
  for (const item of missing) fieldErrors[item.fieldname] = `Vui lòng nhập ${item.label.toLowerCase()}`;
  if (missing.length) error.value = "Còn trường bắt buộc chưa được nhập.";
  return missing.length === 0;
}

async function save() {
  if (!validate()) return;
  saving.value = true;
  try {
    const saved = await api.save(props.meta.doctype, { ...record }, props.name);
    toast(editing.value ? "Đã lưu thay đổi" : "Đã thêm mới");
    emit("saved", saved);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

function requestClose() {
  if (dirty.value && !window.confirm("Có thay đổi chưa lưu. Đóng và bỏ thay đổi?")) return;
  emit("close");
}

async function remove() {
  confirmDelete.busy = true;
  confirmDelete.error = "";
  try {
    await api.remove(props.meta.doctype, props.name);
    confirmDelete.open = false;
    toast("Đã xóa");
    emit("deleted", props.name);
  } catch (e) {
    confirmDelete.error = e.message;
  } finally {
    confirmDelete.busy = false;
  }
}
</script>

<template>
  <Drawer :open="open" :title="title" @close="requestClose">
    <div v-if="loading" class="flex items-center gap-2 py-8 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <template v-else>
      <p v-if="error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
      <FormRenderer
        v-if="Object.keys(record).length"
        :meta="meta"
        :record="record"
        :errors="fieldErrors"
        :editing="editing"
        :read-only="!canWrite"
        :link-filters="(field) => linkFilters(field, record)"
      />
      <component :is="extra" v-if="extra && editing && Object.keys(record).length" :record="record" :meta="meta" @changed="load({ quiet: true })" />
    </template>
    <template #footer>
      <button v-if="canDelete" class="btn mr-auto text-danger" type="button" :disabled="saving" @click="confirmDelete.open = true">
        <Icon name="trash-2" :size="16" /> Xóa
      </button>
      <button class="btn" type="button" @click="requestClose">{{ canWrite ? "Hủy" : "Đóng" }}</button>
      <button v-if="canWrite" class="btn btn-primary" type="button" :disabled="saving || loading || (editing && !dirty)" @click="save">
        <Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> Lưu
      </button>
    </template>
  </Drawer>

  <ConfirmDialog
    :open="confirmDelete.open"
    danger
    title="Xóa bản ghi"
    :message="`Xóa ${meta.label.toLowerCase()} “${record[meta.title_field] || name}”? Thao tác này không thể hoàn tác.`"
    :error="confirmDelete.error"
    confirm-text="Xóa"
    :busy="confirmDelete.busy"
    @confirm="remove"
    @cancel="confirmDelete.open = false"
  />
</template>
