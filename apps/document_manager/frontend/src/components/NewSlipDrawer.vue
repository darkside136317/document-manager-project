<script setup>
import { computed, reactive, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { kindOf } from "../lib/slips.js";
import Drawer from "./Drawer.vue";
import Icon from "./Icon.vue";
import LinkSelect from "./LinkSelect.vue";

// The reading room files a slip for a reader at the counter: pick the reader, add hồ sơ / văn bản, write the
// purpose, then keep it as a draft or send it straight to approval. It follows the same rules as the reader site.
const props = defineProps({ open: { type: Boolean, default: false }, kind: { type: String, default: "usage" } });
const emit = defineEmits(["close", "created"]);

const info = computed(() => kindOf(props.kind));
const form = reactive({ reader: "", purpose: "", notes: "", items: [], file: "", document: "" });
const busy = ref(false);
const error = ref("");

watch(() => props.open, (open) => {
  if (!open) return;
  Object.assign(form, { reader: "", purpose: "", notes: "", items: [], file: "", document: "" });
  error.value = "";
});

function addItem(kind, value) {
  if (!value) return;
  const key = kind === "file" ? "archival_file" : "archive_document";
  if (!form.items.some((i) => i[key] === value && (kind === "file" ? !i.archive_document : true))) {
    form.items.push({ [key]: value, archival_file: kind === "file" ? value : "", archive_document: kind === "document" ? value : "", copy_count: 1, label: value });
  }
  if (kind === "file") form.file = "";
  else form.document = "";
}
const removeItem = (index) => form.items.splice(index, 1);

async function save(submit) {
  error.value = "";
  if (!form.reader) return (error.value = "Hãy chọn độc giả.");
  if (!form.items.length) return (error.value = "Phiếu chưa có hồ sơ, văn bản nào.");
  busy.value = true;
  try {
    const payload = JSON.stringify({
      reader: form.reader, purpose: form.purpose, notes: form.notes,
      items: form.items.map((i) => ({ archival_file: i.archival_file, archive_document: i.archive_document, copy_count: i.copy_count })),
    });
    const result = await api.requests.save(info.value.doctype, payload, null, submit);
    emit("created", result.name);
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Drawer :open="open" :title="`Lập ${info.short} cho độc giả`" width="620px" @close="emit('close')">
    <div class="space-y-4">
      <p v-if="error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
      <div>
        <label class="label" for="ns-reader">Độc giả <span class="text-danger">*</span></label>
        <LinkSelect v-model="form.reader" input-id="ns-reader" doctype="Reader" :clearable="false" />
      </div>
      <div>
        <label class="label" for="ns-purpose">{{ info.purposeLabel }}</label>
        <textarea id="ns-purpose" v-model="form.purpose" class="input" rows="2"></textarea>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label" for="ns-file">Thêm hồ sơ</label>
          <LinkSelect v-model="form.file" input-id="ns-file" doctype="Archival File" @update:model-value="(v) => addItem('file', v)" />
        </div>
        <div>
          <label class="label" for="ns-doc">Thêm văn bản</label>
          <LinkSelect v-model="form.document" input-id="ns-doc" doctype="Archive Document" @update:model-value="(v) => addItem('document', v)" />
        </div>
      </div>
      <div class="table-wrap rounded-md border border-line">
        <table class="data-table">
          <thead><tr><th scope="col">Loại</th><th scope="col">Mã</th><th v-if="kind === 'copy'" scope="col" class="w-24">Số bản</th><th scope="col" class="w-10"><span class="sr-only">Bỏ</span></th></tr></thead>
          <tbody>
            <tr v-if="!form.items.length"><td :colspan="kind === 'copy' ? 4 : 3" class="text-center text-ink-muted">Chưa chọn hồ sơ, văn bản nào</td></tr>
            <tr v-for="(item, index) in form.items" :key="index">
              <td>{{ item.archive_document ? "Văn bản" : "Hồ sơ" }}</td>
              <td class="font-medium">{{ item.archive_document || item.archival_file }}</td>
              <td v-if="kind === 'copy'"><input v-model.number="item.copy_count" class="input" type="number" min="1" :aria-label="`Số bản của ${item.label}`" /></td>
              <td><button class="btn btn-ghost btn-icon" type="button" :aria-label="`Bỏ ${item.label}`" @click="removeItem(index)"><Icon name="trash-2" :size="16" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div>
        <label class="label" for="ns-notes">Ghi chú</label>
        <textarea id="ns-notes" v-model="form.notes" class="input" rows="2"></textarea>
      </div>
    </div>
    <template #footer>
      <button class="btn" type="button" :disabled="busy" @click="emit('close')">Hủy</button>
      <button class="btn" type="button" :disabled="busy" @click="save(false)">Lưu nháp</button>
      <button class="btn btn-primary" type="button" :disabled="busy" @click="save(true)">
        <Icon :name="busy ? 'loader' : 'send'" :size="16" :spin="busy" /> Gửi duyệt
      </button>
    </template>
  </Drawer>
</template>
