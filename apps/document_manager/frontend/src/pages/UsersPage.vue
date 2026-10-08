<script setup>
import { computed, onMounted, ref, watch } from "vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import OneTimeLinkDialog from "../components/OneTimeLinkDialog.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { blankUser, canEditUser, changedValues, sortRoles, toggleValue, userProblem, userToForm } from "../lib/admin.js";
import { boot } from "../lib/boot.js";
import { debounce, formatDateTime } from "../lib/format.js";
import { absoluteLink } from "../lib/registrations.js";
import { toast } from "../lib/toast.js";

// Staff accounts: search and filter, create, edit roles and groups, lock, hand over a set-password link, delete.
const roles = ref([]);
const groups = ref([]);
const list = ref({ data: [], total: 0, page: 1, page_size: 20 });
const filters = ref({ search: "", role: "", group: "", enabled: "" });
const loading = ref(false);
const error = ref("");

const drawer = ref(false);
const editing = ref(null); // the user being edited, null when creating
const form = ref(blankUser());
const saving = ref(false);
const formError = ref("");
const confirm = ref("");
const link = ref({ open: false, url: "", user: "" });

const roleLabel = (role) => roles.value.find((r) => r.role === role)?.label || role;
const creating = computed(() => !editing.value);
const locked = computed(() => !creating.value && !canEditUser(editing.value, boot.user));
const problem = computed(() => userProblem(form.value, creating.value));
const dirty = computed(() => (creating.value ? true : Object.keys(changedValues(userToForm(editing.value), form.value)).length > 0));

let ticket = 0;
async function load(page = 1) {
  const mine = ++ticket; // an answer to a filter the user has since changed must not replace the list
  loading.value = true;
  try {
    const f = filters.value;
    const answer = await api.users.list({ search: f.search || undefined, role: f.role || undefined, group: f.group || undefined, enabled: f.enabled === "" ? undefined : f.enabled, page });
    if (mine !== ticket) return;
    list.value = answer;
    error.value = "";
  } catch (e) {
    if (mine === ticket) error.value = e.message;
  } finally {
    if (mine === ticket) loading.value = false;
  }
}
const reload = debounce(() => load(1), 300);
watch(() => filters.value.search, reload);
watch(() => [filters.value.role, filters.value.group, filters.value.enabled], () => load(1));

onMounted(async () => {
  try {
    [roles.value, groups.value] = await Promise.all([api.users.roles(), api.list("Staff Group", { page_size: 100 }).then((r) => r.data)]);
  } catch (e) {
    error.value = e.message;
  }
  load(1);
});

function openNew() {
  editing.value = null;
  form.value = blankUser();
  formError.value = "";
  drawer.value = true;
}
function openUser(user) {
  editing.value = user;
  form.value = userToForm(user);
  formError.value = "";
  drawer.value = true;
}
async function save() {
  if (problem.value) {
    formError.value = problem.value;
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    if (creating.value) {
      const out = await api.users.save({ ...form.value });
      toast("Đã tạo tài khoản");
      drawer.value = false;
      link.value = { open: true, url: absoluteLink(out.set_password_path), user: out.name };
    } else {
      editing.value = await api.users.save(changedValues(userToForm(editing.value), form.value), editing.value.name);
      form.value = userToForm(editing.value);
      toast("Đã lưu thay đổi");
    }
    await load(list.value.page);
  } catch (e) {
    formError.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function toggleEnabled() {
  try {
    editing.value = await api.users.setEnabled(editing.value.name, !editing.value.enabled);
    form.value = userToForm(editing.value);
    toast(editing.value.enabled ? "Đã mở khóa tài khoản" : "Đã khóa tài khoản");
    await load(list.value.page);
  } catch (e) {
    formError.value = e.message;
  }
}
async function issueLink() {
  try {
    const out = await api.users.link(editing.value.name);
    link.value = { open: true, url: absoluteLink(out.set_password_path), user: out.user };
  } catch (e) {
    formError.value = e.message;
  }
}
async function remove() {
  try {
    await api.users.remove(editing.value.name);
    confirm.value = "";
    drawer.value = false;
    toast("Đã xóa tài khoản");
    await load(1);
  } catch (e) {
    formError.value = e.message;
    confirm.value = "";
  }
}
</script>

<template>
  <PageHeader title="Người dùng" subtitle="Tài khoản cán bộ: thêm, sửa, khóa, cấp vai trò và nhóm. Tài khoản độc giả được quản lý ở mục Độc giả.">
    <RouterLink class="btn" to="/quan-tri/nhom-can-bo"><Icon name="users" :size="16" /> Nhóm cán bộ</RouterLink>
    <RouterLink class="btn" to="/quan-tri/phan-quyen"><Icon name="shield-check" :size="16" /> Phân quyền</RouterLink>
    <button class="btn btn-primary" type="button" @click="openNew"><Icon name="user-plus" :size="16" /> Thêm người dùng</button>
  </PageHeader>

  <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

  <section class="card">
    <header class="flex flex-wrap items-end gap-3 border-b border-line px-4 py-3">
      <label class="min-w-[14rem] flex-1 text-sm"><span class="sr-only">Tìm người dùng</span>
        <input v-model="filters.search" class="input" type="search" placeholder="Tìm theo tên, email, điện thoại…" aria-label="Tìm người dùng" /></label>
      <label class="text-sm"><span class="sr-only">Vai trò</span>
        <select v-model="filters.role" class="input w-auto" aria-label="Lọc theo vai trò"><option value="">Mọi vai trò</option><option v-for="r in roles" :key="r.role" :value="r.role">{{ r.label }}</option></select></label>
      <label class="text-sm"><span class="sr-only">Nhóm</span>
        <select v-model="filters.group" class="input w-auto" aria-label="Lọc theo nhóm"><option value="">Mọi nhóm</option><option v-for="g in groups" :key="g.name" :value="g.name">{{ g.group_name || g.name }}</option></select></label>
      <label class="text-sm"><span class="sr-only">Tình trạng</span>
        <select v-model="filters.enabled" class="input w-auto" aria-label="Lọc theo tình trạng"><option value="">Mọi tình trạng</option><option value="1">Đang hoạt động</option><option value="0">Đã khóa</option></select></label>
    </header>
    <div v-if="loading && !list.data.length" class="space-y-2 p-5"><div v-for="n in 5" :key="n" class="h-9 animate-pulse rounded bg-surface-muted"></div></div>
    <EmptyState v-else-if="!list.data.length" icon="users" title="Không có người dùng nào" text="Thử bớt điều kiện lọc hoặc thêm người dùng mới." />
    <div v-else class="table-wrap" :class="{ 'opacity-60': loading }">
      <table class="data-table">
        <caption class="sr-only">Danh sách người dùng</caption>
        <thead><tr><th scope="col">Họ và tên</th><th scope="col">Vai trò</th><th scope="col">Nhóm</th><th scope="col">Tình trạng</th><th scope="col">Đăng nhập gần nhất</th></tr></thead>
        <tbody>
          <tr v-for="user in list.data" :key="user.name" class="is-clickable" tabindex="0" @click="openUser(user)" @keydown.enter="openUser(user)">
            <td><span class="block font-medium">{{ user.full_name }}<span v-if="user.is_me" class="badge badge-info ml-2">Bạn</span></span><span class="block text-xs text-ink-muted">{{ user.name }}</span></td>
            <td>
              <span v-for="r in sortRoles(user.roles)" :key="r" class="badge badge-muted mr-1">{{ roleLabel(r) }}</span>
              <span v-if="user.protected" class="badge badge-warning" title="Có quyền quản trị toàn hệ thống">Quản trị hệ thống</span>
            </td>
            <td class="text-sm text-ink-soft">{{ user.groups.join(", ") }}</td>
            <td><StatusBadge :value="user.enabled ? 'Hoàn thành' : 'Đã hủy'" /><span class="sr-only">{{ user.enabled ? "Đang hoạt động" : "Đã khóa" }}</span><span class="ml-2 text-xs text-ink-muted">{{ user.enabled ? "Hoạt động" : "Đã khóa" }}</span></td>
            <td class="whitespace-nowrap text-sm text-ink-muted">{{ formatDateTime(user.last_login) || "Chưa đăng nhập" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginationBar v-if="list.total" :page="list.page" :page-size="list.page_size" :total="list.total" @change="load" />
  </section>

  <Drawer :open="drawer" :title="creating ? 'Thêm người dùng' : editing?.full_name || ''" width="560px" @close="drawer = false">
    <form class="space-y-5" @submit.prevent="save">
      <p v-if="formError" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ formError }}</p>
      <p v-if="locked" class="m-0 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning" role="status">Tài khoản này có quyền quản trị toàn hệ thống: chỉ System Manager mới thay đổi được.</p>
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="block text-sm sm:col-span-2"><span class="label">Email đăng nhập<span v-if="creating" class="text-danger"> *</span></span>
          <input v-model="form.email" class="input" type="email" :disabled="!creating" autocomplete="off" /></label>
        <label class="block text-sm"><span class="label">Tên<span class="text-danger"> *</span></span><input v-model="form.first_name" class="input" type="text" :disabled="locked" /></label>
        <label class="block text-sm"><span class="label">Họ</span><input v-model="form.last_name" class="input" type="text" :disabled="locked" /></label>
        <label class="block text-sm sm:col-span-2"><span class="label">Điện thoại</span><input v-model="form.phone" class="input" type="tel" :disabled="locked" /></label>
      </div>

      <fieldset class="space-y-2" :disabled="locked">
        <legend class="label">Vai trò</legend>
        <label v-for="r in roles" :key="r.role" class="flex cursor-pointer items-start gap-2 rounded-md border border-line p-3 text-sm" :class="{ 'bg-primary-soft': form.roles.includes(r.role) }">
          <input type="checkbox" class="mt-0.5 h-4 w-4 accent-[var(--dm-primary)]" :checked="form.roles.includes(r.role)" @change="form.roles = toggleValue(form.roles, r.role)" />
          <span><strong>{{ r.label }}</strong> <span class="badge badge-muted ml-1">{{ r.group }}</span><span class="mt-0.5 block text-xs text-ink-muted">{{ r.description }}</span></span>
        </label>
      </fieldset>

      <fieldset v-if="groups.length" class="space-y-2" :disabled="locked">
        <legend class="label">Nhóm</legend>
        <label v-for="g in groups" :key="g.name" class="mr-4 inline-flex cursor-pointer items-center gap-2 text-sm">
          <input type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" :checked="form.groups.includes(g.name)" @change="form.groups = toggleValue(form.groups, g.name)" /> {{ g.group_name || g.name }}
        </label>
      </fieldset>

      <label v-if="!creating && !locked" class="flex cursor-pointer items-center gap-2 text-sm font-medium">
        <input v-model="form.enabled" type="checkbox" class="h-4 w-4 accent-[var(--dm-primary)]" :true-value="1" :false-value="0" /> Tài khoản đang hoạt động
      </label>
      <p v-if="creating" class="m-0 text-xs text-ink-muted">Sau khi tạo, hệ thống đưa một liên kết dùng một lần để người dùng tự đặt mật khẩu. Liên kết chỉ hiện một lần.</p>
    </form>
    <template #footer>
      <button v-if="!creating && !locked" class="btn mr-auto" type="button" @click="issueLink"><Icon name="key-round" :size="16" /> Cấp liên kết mật khẩu</button>
      <button v-if="!creating && !locked" class="btn" type="button" @click="toggleEnabled"><Icon name="lock-keyhole" :size="16" /> {{ editing.enabled ? "Khóa" : "Mở khóa" }}</button>
      <button v-if="!creating && !locked" class="btn text-danger" type="button" @click="confirm = 'remove'"><Icon name="trash-2" :size="16" /> Xóa</button>
      <button class="btn" type="button" @click="drawer = false">Đóng</button>
      <button v-if="!locked" class="btn btn-primary" type="button" :disabled="saving || !dirty" @click="save"><Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> {{ creating ? "Tạo" : "Lưu" }}</button>
    </template>
  </Drawer>

  <ConfirmDialog :open="confirm === 'remove'" danger title="Xóa tài khoản?" confirm-text="Xóa" message="Chỉ xóa được tài khoản chưa có dữ liệu liên quan; nếu đã có, hãy khóa tài khoản thay vì xóa." @confirm="remove" @cancel="confirm = ''" />
  <OneTimeLinkDialog :open="link.open" :url="link.url" :user="link.user" @close="link.open = false" />
</template>
