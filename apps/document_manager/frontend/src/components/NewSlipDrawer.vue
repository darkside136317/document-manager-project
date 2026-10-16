<script setup>
import { computed, reactive, ref, watch } from "vue";
import { api } from "../lib/api.js";
import { kindOf } from "../lib/slips.js";
import Drawer from "./Drawer.vue";
import Icon from "./Icon.vue";
import LinkSelect from "./LinkSelect.vue";

// The reading room files a slip for a reader at the counter: pick the reader, add hồ sơ / văn bản, write the
// purpose, then keep it as a draft or send it straight to approval. It follows the same rules as the reader site:
// each item is checked against the reader's own rights as soon as it is added (api.slips.prepare), not only on sending.
const props = defineProps({ open: { type: Boolean, default: false }, kind: { type: String, default: "usage" } });
const emit = defineEmits(["close", "created"]);

const info = computed(() => kindOf(props.kind));
const form = reactive({ reader: "", purpose: "", notes: "", items: [] });
const picker = reactive({ file: "", document: "", key: 0 }); // `key` remounts the pickers so they show empty again
const prepared = reactive({ purposes: [], requirePurpose: false, reader: null, checking: false });
let checkRun = 0; // only the answer to the latest question counts
const busy = ref(false);
const error = ref("");

watch(() => props.open, (open) => {
  if (!open) return;
  Object.assign(form, { reader: "", purpose: "", notes: "", items: [] });
  Object.assign(prepared, { purposes: [], requirePurpose: false, reader: null, checking: false });
  error.value = "";
  check();
});

const keyOf = (i) => `${i.archive_document ? "document" : "file"}:${i.archive_document || i.archival_file}`;
const problems = computed(() => form.items.filter((i) => i.problem));

/** Ask the server about the reader and every item: titles, the reader's group and fonds, and what would be refused. */
async function check() {
  const run = ++checkRun;
  prepared.checking = true;
  try {
    const result = await api.slips.prepare(props.kind, form.reader, form.items.map((i) => ({ archival_file: i.archival_file, archive_document: i.archive_document })));
    if (run !== checkRun) return;
    prepared.purposes = result.purposes || [];
    prepared.requirePurpose = Boolean(result.require_purpose);
    prepared.reader = result.reader;
    const byKey = Object.fromEntries((result.items || []).map((i) => [keyOf(i), i]));
    for (const item of form.items) Object.assign(item, byKey[keyOf(item)] || {}, { copy_count: item.copy_count, copy_form: item.copy_form, page_range: item.page_range });
  } catch (e) {
    error.value = e.message;
  } finally {
    if (run === checkRun) prepared.checking = false;
  }
}
watch(() => form.reader, () => check());

function addItem(kind, value) {
  if (!value) return;
  const item = kind === "file" ? { archival_file: value, archive_document: "" } : { archival_file: "", archive_document: value };
  if (!form.items.some((i) => keyOf(i) === keyOf(item))) {
    form.items.push({ ...item, title: value, number: "", level: "", fonds_name: "", problem: "", copy_count: 1, copy_form: "Bản giấy", page_range: "" });
    check();
  }
  Object.assign(picker, { file: "", document: "", key: picker.key + 1 });
}
const removeItem = (index) => form.items.splice(index, 1);

async function save(submit) {
  error.value = "";
  if (!form.reader) return (error.value = "Hãy chọn độc giả.");
  if (!form.items.length) return (error.value = "Phiếu chưa có hồ sơ, văn bản nào.");
  if (problems.value.length) return (error.value = "Bỏ các dòng độc giả không được khai thác (đánh dấu đỏ) rồi lưu lại.");
  if (submit && prepared.requirePurpose && !form.purpose.trim()) return (error.value = `Hãy nhập ${info.value.purposeLabel.toLowerCase()}.`);
  busy.value = true;
  try {
    const payload = JSON.stringify({
      reader: form.reader, purpose: form.purpose, notes: form.notes,
      items: form.items.map((i) => ({ archival_file: i.archival_file, archive_document: i.archive_document, copy_count: i.copy_count, copy_form: i.copy_form, page_range: i.page_range })),
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
  <Drawer :open="open" :title="`Lập ${info.short} cho độc giả`" width="660px" @close="emit('close')">
    <div class="space-y-4">
      <p v-if="error" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
      <div>
        <label class="label" for="ns-reader">Độc giả <span class="text-danger">*</span></label>
        <LinkSelect v-model="form.reader" input-id="ns-reader" doctype="Reader" :clearable="false" />
        <div v-if="prepared.reader" class="mt-2 rounded-md bg-surface-muted px-3 py-2 text-sm" aria-live="polite">
          <p class="m-0"><strong>{{ prepared.reader.full_name }}</strong><span v-if="prepared.reader.contact" class="text-ink-muted"> · {{ prepared.reader.contact }}</span></p>
          <p class="m-0 text-ink-muted">Nhóm: {{ prepared.reader.group || "—" }}</p>
          <p class="m-0 text-ink-muted">Phông được khai thác:
            {{ prepared.reader.fonds.length ? prepared.reader.fonds.map((f) => f.until ? `${f.name} (đến ${f.until})` : f.name).join(", ") : "chưa có phông nào" }}</p>
          <p v-for="w in prepared.reader.warnings" :key="w" class="m-0 mt-1 flex items-start gap-1.5 text-warning"><Icon name="alert-triangle" :size="14" class="mt-0.5 shrink-0" /><span>{{ w }}</span></p>
        </div>
      </div>
      <div>
        <label class="label" for="ns-purpose">{{ info.purposeLabel }}</label>
        <div v-if="prepared.purposes.length" class="mb-2 flex flex-wrap gap-1.5" role="group" aria-label="Mục đích gợi ý">
          <button v-for="p in prepared.purposes" :key="p" class="btn btn-sm" :class="{ 'btn-primary': form.purpose === p }" type="button" :aria-pressed="form.purpose === p" @click="form.purpose = p">{{ p }}</button>
        </div>
        <textarea id="ns-purpose" v-model="form.purpose" class="input" rows="2" placeholder="Chọn một mục đích gợi ý hoặc tự nhập"></textarea>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label" for="ns-file">Thêm hồ sơ</label>
          <LinkSelect :key="`f${picker.key}`" v-model="picker.file" input-id="ns-file" doctype="Archival File" @update:model-value="(v) => addItem('file', v)" />
        </div>
        <div>
          <label class="label" for="ns-doc">Thêm văn bản</label>
          <LinkSelect :key="`d${picker.key}`" v-model="picker.document" input-id="ns-doc" doctype="Archive Document" @update:model-value="(v) => addItem('document', v)" />
        </div>
      </div>
      <div class="table-wrap rounded-md border border-line">
        <table class="data-table">
          <thead><tr><th scope="col">Tài liệu</th><th v-if="kind === 'copy'" scope="col" class="w-24">Số bản</th><th v-if="kind === 'copy'" scope="col">Hình thức, trang</th><th scope="col" class="w-10"><span class="sr-only">Bỏ</span></th></tr></thead>
          <tbody>
            <tr v-if="!form.items.length"><td :colspan="kind === 'copy' ? 4 : 2" class="text-center text-ink-muted">Chưa chọn hồ sơ, văn bản nào</td></tr>
            <tr v-for="(item, index) in form.items" :key="keyOf(item)" :class="{ 'bg-danger-soft': item.problem }">
              <td>
                <div class="font-medium">{{ item.title }}</div>
                <div class="text-xs text-ink-muted">{{ [item.kind || (item.archive_document ? "Văn bản" : "Hồ sơ"), item.number && `số ${item.number}`, item.fonds_name, item.level].filter(Boolean).join(" · ") }}</div>
                <div v-if="item.problem" class="flex items-start gap-1 text-xs text-danger" role="alert"><Icon name="alert-triangle" :size="12" class="mt-0.5 shrink-0" /><span>Không lập được: {{ item.problem }}</span></div>
              </td>
              <td v-if="kind === 'copy'"><input v-model.number="item.copy_count" class="input" type="number" min="1" :aria-label="`Số bản của ${item.title}`" /></td>
              <td v-if="kind === 'copy'" class="space-y-1">
                <select v-model="item.copy_form" class="input" :aria-label="`Hình thức sao của ${item.title}`"><option>Bản giấy</option><option>Bản số</option></select>
                <input v-model="item.page_range" class="input" type="text" maxlength="60" placeholder="Trang: toàn bộ, hoặc 1-5, 8" :aria-label="`Trang cần sao của ${item.title}`" />
              </td>
              <td><button class="btn btn-ghost btn-icon" type="button" :aria-label="`Bỏ ${item.title}`" @click="removeItem(index)"><Icon name="trash-2" :size="16" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="form.reader && prepared.reader?.notes?.length" class="m-0 text-xs text-ink-muted">{{ prepared.reader.notes.join(" · ") }}</p>
      <div>
        <label class="label" for="ns-notes">Ghi chú</label>
        <textarea id="ns-notes" v-model="form.notes" class="input" rows="2"></textarea>
      </div>
    </div>
    <template #footer>
      <span v-if="prepared.checking" class="mr-auto text-sm text-ink-muted"><Icon name="loader" :size="14" spin /> Đang kiểm tra…</span>
      <button class="btn" type="button" :disabled="busy" @click="emit('close')">Hủy</button>
      <button class="btn" type="button" :disabled="busy || problems.length > 0" @click="save(false)">Lưu nháp</button>
      <button class="btn btn-primary" type="button" :disabled="busy || problems.length > 0" @click="save(true)">
        <Icon :name="busy ? 'loader' : 'send'" :size="16" :spin="busy" /> Gửi duyệt
      </button>
    </template>
  </Drawer>
</template>
