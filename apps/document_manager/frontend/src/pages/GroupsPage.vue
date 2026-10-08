<script setup>
import { computed, onMounted, ref } from "vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { toggleValue } from "../lib/admin.js";
import { toast } from "../lib/toast.js";

// Staff groups: a name, the roles every member gets, and who the members are. (The generic form cannot pick users or roles.)
const groups = ref([]);
const roles = ref([]);
const staff = ref([]);
const loading = ref(true);
const error = ref("");
const drawer = ref(false);
const form = ref({ name: "", group_name: "", description: "", roles: [], members: [], modified: "" });
const saving = ref(false);
const formError = ref("");
const confirm = ref(false);
const filter = ref("");

const creating = computed(() => !form.value.name);
const roleLabel = (role) => roles.value.find((r) => r.role === role)?.label || role;
const visibleStaff = computed(() => staff.value.filter((u) => !filter.value || `${u.full_name} ${u.name}`.toLowerCase().includes(filter.value.toLowerCase())));

async function load() {
  loading.value = true;
  try {
    const list = await api.list("Staff Group", { page_size: 100 });
    groups.value = await Promise.all(list.data.map((g) => api.get("Staff Group", g.name)));
    error.value = "";
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
onMounted(async () => {
  try {
    [roles.value, staff.value] = await Promise.all([api.users.roles(), api.users.list({ page_size: 100 }).then((r) => r.data)]);
  } catch (e) {
    error.value = e.message;
  }
  load();
});

function openGroup(group) {
  form.value = group
    ? { name: group.name, group_name: group.group_name, description: group.description || "", roles: group.roles.map((r) => r.role), members: group.members.map((m) => m.user), modified: group.modified }
    : { name: "", group_name: "", description: "", roles: [], members: [], modified: "" };
  formError.value = "";
  filter.value = "";
  drawer.value = true;
}
async function save() {
  if (!form.value.group_name.trim()) {
    formError.value = "Nhập tên nhóm";
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    const values = { group_name: form.value.group_name.trim(), description: form.value.description, roles: form.value.roles.map((role) => ({ role })), members: form.value.members.map((user) => ({ user })) };
    await api.save("Staff Group", creating.value ? values : { ...values, modified: form.value.modified }, form.value.name || null);
    toast(creating.value ? "Đã tạo nhóm" : "Đã lưu nhóm");
    drawer.value = false;
    await load();
  } catch (e) {
    formError.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function remove() {
  try {
    await api.remove("Staff Group", form.value.name);
    confirm.value = false;
    drawer.value = false;
    toast("Đã xóa nhóm");
    await load();
  } catch (e) {
    formError.value = e.message;
    confirm.value = false;
  }
}
</script>

<template>
  <PageHeader title="Nhóm cán bộ" subtitle="Gom cán bộ thành nhóm và cấp vai trò đồng loạt. Bỏ một người khỏi nhóm không tự thu hồi vai trò: chỉnh ở màn hình Người dùng.">
    <RouterLink class="btn" to="/quan-tri/nguoi-dung"><Icon name="users" :size="16" /> Người dùng</RouterLink>
    <button class="btn btn-primary" type="button" @click="openGroup(null)"><Icon name="plus" :size="16" /> Thêm nhóm</button>
  </PageHeader>

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
  <section class="card">
    <div v-if="loading" class="space-y-2 p-5"><div v-for="n in 3" :key="n" class="h-9 animate-pulse rounded bg-surface-muted"></div></div>
    <EmptyState v-else-if="!groups.length" icon="users" title="Chưa có nhóm nào" text="Tạo nhóm để cấp vai trò cho nhiều cán bộ cùng lúc." />
    <div v-else class="table-wrap">
      <table class="data-table">
        <caption class="sr-only">Các nhóm cán bộ</caption>
        <thead><tr><th scope="col">Tên nhóm</th><th scope="col">Vai trò</th><th scope="col">Thành viên</th></tr></thead>
        <tbody>
          <tr v-for="group in groups" :key="group.name" class="is-clickable" tabindex="0" @click="openGroup(group)" @keydown.enter="openGroup(group)">
            <td><span class="block font-medium">{{ group.group_name }}</span><span class="block text-xs text-ink-muted">{{ group.description }}</span></td>
            <td><span v-for="r in group.roles" :key="r.role" class="badge badge-muted mr-1">{{ roleLabel(r.role) }}</span></td>
            <td class="text-sm text-ink-soft">{{ group.members.length }} người</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <Drawer :open="drawer" :title="creating ? 'Thêm nhóm' : form.group_name" width="560px" @close="drawer = false">
    <form class="space-y-5" @submit.prevent="save">
      <p v-if="formError" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ formError }}</p>
      <label class="block text-sm"><span class="label">Tên nhóm<span class="text-danger"> *</span></span><input v-model="form.group_name" class="input" type="text" :disabled="!creating" /></label>
      <label class="block text-sm"><span class="label">Mô tả</span><textarea v-model="form.description" class="input" rows="2"></textarea></label>
      <fieldset class="space-y-2">
        <legend class="label">Vai trò cấp cho các thành viên</legend>
        <label v-for="r in roles" :key="r.role" class="flex cursor-pointer items-start gap-2 text-sm">
          <input type="checkbox" class="mt-0.5 h-4 w-4 accent-[var(--dm-primary)]" :checked="form.roles.includes(r.role)" @change="form.roles = toggleValue(form.roles, r.role)" />
          <span><strong>{{ r.label }}</strong><span class="block text-xs text-ink-muted">{{ r.description }}</span></span>
        </label>
      </fieldset>
      <fieldset class="space-y-2">
        <legend class="label">Thành viên ({{ form.members.length }})</legend>
        <input v-model="filter" class="input" type="search" placeholder="Tìm cán bộ…" aria-label="Tìm cán bộ" />
        <div class="max-h-64 space-y-1 overflow-y-auto rounded-md border border-line p-2">
          <label v-for="u in visibleStaff" :key="u.name" class="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" :checked="form.members.includes(u.name)" :disabled="u.protected" @change="form.members = toggleValue(form.members, u.name)" />
            <span>{{ u.full_name }} <span class="text-xs text-ink-muted">{{ u.name }}</span></span>
          </label>
        </div>
      </fieldset>
    </form>
    <template #footer>
      <button v-if="!creating" class="btn mr-auto text-danger" type="button" @click="confirm = true"><Icon name="trash-2" :size="16" /> Xóa</button>
      <button class="btn" type="button" @click="drawer = false">Đóng</button>
      <button class="btn btn-primary" type="button" :disabled="saving" @click="save"><Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> Lưu</button>
    </template>
  </Drawer>
  <ConfirmDialog :open="confirm" danger title="Xóa nhóm?" confirm-text="Xóa" message="Nhóm bị xóa; các thành viên giữ nguyên vai trò đã được cấp." @confirm="remove" @cancel="confirm = false" />
</template>
