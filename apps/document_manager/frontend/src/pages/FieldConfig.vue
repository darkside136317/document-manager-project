<script setup>
import { computed, onMounted, ref } from "vue";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/api.js";
import { pageTitle } from "../lib/page.js";

const BASE = "document_manager.document_manager.api.digitization";
const fields = ref({});
const current = ref("");
const busy = ref(false);
const error = ref("");
const notice = ref("");
const fresh = ref({ fieldname: "", label: "", fieldtype: "Data" });
const doctypes = computed(() => Object.keys(fields.value));

async function load() {
  const result = await call(`${BASE}.configuration`);
  fields.value = result.fields || {};
  if (!current.value || !fields.value[current.value]) current.value = doctypes.value[0] || "";
}
onMounted(async () => { pageTitle.value = "Cấu hình trường dữ liệu"; try { await load(); } catch (e) { error.value = e.message; } });

async function save(field) {
  busy.value = true; error.value = ""; notice.value = "";
  try {
    await call(`${BASE}.save_field`, { doctype: current.value, fieldname: field.fieldname,
      values: { label: field.label, visibility: field.visibility, position: Number(field.position),
        required: field.required } }, { post: true });
    notice.value = `Đã lưu ${field.label}.`;
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
async function add() {
  busy.value = true; error.value = ""; notice.value = "";
  try {
    await call(`${BASE}.add_field`, { doctype: current.value, ...fresh.value }, { post: true });
    fresh.value = { fieldname: "", label: "", fieldtype: "Data" };
    await load(); notice.value = "Đã thêm trường dữ liệu.";
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
async function remove(field) {
  if (!window.confirm(`Xóa trường ${field.label}? Chỉ trường tùy chỉnh chưa có dữ liệu mới xóa được.`)) return;
  busy.value = true; error.value = "";
  try {
    await call(`${BASE}.remove_field`, { doctype: current.value, fieldname: field.fieldname }, { post: true });
    await load(); notice.value = "Đã xóa trường dữ liệu.";
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}
</script>

<template>
  <PageHeader title="Cấu hình trường dữ liệu" subtitle="Quản trị tên, thứ tự, chế độ hiển thị và schema AI trên cùng một dữ liệu lưu trữ" />
  <p v-if="error" class="rounded bg-danger-soft p-3 text-danger" role="alert">{{ error }}</p>
  <p v-if="notice" class="rounded bg-primary-soft p-3" role="status">{{ notice }}</p>
  <div class="card p-4">
    <label class="block text-sm font-medium" for="field-doctype">Danh mục</label>
    <select id="field-doctype" v-model="current" class="input mt-1 max-w-md"><option v-for="name in doctypes" :key="name" :value="name">{{ name }}</option></select>
    <p class="text-sm text-ink-muted">Trường trong cây hồ sơ được đánh dấu Số hóa hoặc Cả hai sẽ được chụp thành schema khi gửi job. Trường bắt buộc luôn hiện ở cả hai chế độ.</p>
    <div class="overflow-x-auto">
      <table class="w-full text-sm"><thead><tr class="border-b border-line text-left"><th class="p-2">Mã trường</th><th class="p-2">Tên hiển thị</th><th class="p-2">Chế độ</th><th class="p-2">Thứ tự</th><th class="p-2">Thao tác</th></tr></thead>
        <tbody><tr v-for="field in fields[current] || []" :key="field.fieldname" class="border-b border-line">
          <td class="p-2 font-mono text-xs">{{ field.fieldname }}</td>
          <td class="p-2"><input v-model="field.label" class="input min-w-40" :aria-label="`Tên ${field.fieldname}`" /></td>
          <td class="p-2"><select v-model="field.visibility" class="input"><option value="exploitation">Khai thác</option><option value="digitization">Số hóa</option><option value="both">Cả hai</option></select></td>
          <td class="p-2"><input v-model.number="field.position" class="input w-20" type="number" min="0" max="10000" /></td>
          <td class="p-2 whitespace-nowrap"><button class="btn" type="button" :disabled="busy" @click="save(field)">Lưu</button> <button v-if="field.fieldname.startsWith('custom_')" class="btn" type="button" :disabled="busy" @click="remove(field)">Xóa</button></td>
        </tr></tbody>
      </table>
    </div>
    <form class="mt-5 flex flex-wrap items-end gap-2" @submit.prevent="add">
      <label class="text-sm">Mã trường<input v-model="fresh.fieldname" class="input mt-1" placeholder="custom_ma_ho_so" required pattern="custom_[a-z][a-z0-9_]+" /></label>
      <label class="text-sm">Tên trường<input v-model="fresh.label" class="input mt-1" required /></label>
      <label class="text-sm">Kiểu<select v-model="fresh.fieldtype" class="input mt-1"><option>Data</option><option>Small Text</option><option>Text</option><option>Int</option><option>Float</option><option>Date</option><option>Check</option></select></label>
      <button class="btn btn-primary" type="submit" :disabled="busy || !current">Thêm trường</button>
    </form>
  </div>
</template>
