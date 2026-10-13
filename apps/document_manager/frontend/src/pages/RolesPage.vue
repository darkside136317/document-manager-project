<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { MATRIX_COLUMNS, changedMatrix, checkedCapabilities, describeChanges, editableMatrix, toggleCell, toggleValue } from "../lib/admin.js";
import { toast } from "../lib/toast.js";

// Permission groups (nhóm quyền): what each group may do with each kind of data, which functions it may use, who holds it.
// Only administrators reach this screen; the server checks every change again.
const route = useRoute();
const router = useRouter();
const groups = ref([]);
const group = ref(null);
const loading = ref(true);
const error = ref("");
const tab = ref("data");
const form = ref({ label: "", description: "", group: "Tác nghiệp" });
const matrix = ref({});
const capabilities = ref([]);
const saving = ref(false);
const confirm = ref(""); // "save" | "remove" | "reset" | "leave"
const pendingRole = ref("");
const creating = ref(null); // {label, description, group, copy_from}
const createError = ref("");

const TABS = [["data", "Quyền trên dữ liệu", "database"], ["functions", "Chức năng", "shield-check"], ["members", "Thành viên", "users"]];
const locked = computed(() => Boolean(group.value?.locked));
const changes = computed(() => (group.value ? describeChanges(group.value, matrix.value, capabilities.value, group.value.columns) : []));
const detailsChanged = computed(() => group.value && (form.value.label !== group.value.label || form.value.description !== group.value.description || form.value.group !== group.value.group));
const dirty = computed(() => !locked.value && (changes.value.length > 0 || detailsChanged.value));

async function loadGroups() {
  groups.value = await api.permissions.list();
}

function adopt(data) {
  group.value = data;
  form.value = { label: data.label, description: data.description, group: data.group };
  matrix.value = editableMatrix(data);
  capabilities.value = checkedCapabilities(data);
}

async function open(role) {
  error.value = "";
  try {
    adopt(await api.permissions.get(role));
    if (route.query.role !== role) router.replace({ query: { ...route.query, role } });
  } catch (e) {
    error.value = e.message;
  }
}

function choose(role) {
  if (role === group.value?.role) return;
  if (dirty.value) {
    pendingRole.value = role;
    confirm.value = "leave";
    return;
  }
  open(role);
}

onMounted(async () => {
  try {
    await loadGroups();
    const wanted = groups.value.find((g) => g.role === route.query.role) || groups.value[0];
    if (wanted) await open(wanted.role);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
});

// only the columns that mean something for at least one kind of data of the section
const sectionColumns = (section) => MATRIX_COLUMNS.filter((col) => section.rows.some((row) => row.columns.includes(col)));
const toggle = (doctype, key, value) => { matrix.value = { ...matrix.value, [doctype]: toggleCell(matrix.value[doctype] || {}, key, value) }; };

async function save() {
  saving.value = true;
  try {
    const values = { ...form.value, capabilities: capabilities.value, matrix: changedMatrix(editableMatrix(group.value), matrix.value), modified: group.value.modified };
    adopt(await api.permissions.save(group.value.role, values));
    await loadGroups();
    toast("Đã lưu nhóm quyền");
    confirm.value = "";
  } catch (e) {
    error.value = e.message;
    confirm.value = "";
  } finally {
    saving.value = false;
  }
}

async function remove() {
  try {
    await api.permissions.remove(group.value.role);
    confirm.value = "";
    group.value = null;
    await loadGroups();
    if (groups.value[0]) await open(groups.value[0].role);
    toast("Đã xóa nhóm quyền");
  } catch (e) {
    error.value = e.message;
    confirm.value = "";
  }
}

async function reset() {
  try {
    adopt(await api.permissions.reset(group.value.role));
    confirm.value = "";
    toast("Đã khôi phục quyền mặc định");
  } catch (e) {
    error.value = e.message;
    confirm.value = "";
  }
}

function startCreate(copyFrom = "") {
  createError.value = "";
  creating.value = { label: "", description: "", group: "Tác nghiệp", copy_from: copyFrom };
}

async function create() {
  createError.value = "";
  try {
    const data = await api.permissions.create({ ...creating.value, copy_from: creating.value.copy_from || null });
    creating.value = null;
    await loadGroups();
    adopt(data);
    router.replace({ query: { ...route.query, role: data.role } });
    toast("Đã tạo nhóm quyền");
  } catch (e) {
    createError.value = e.message;
  }
}

function leave() {
  confirm.value = "";
  open(pendingRole.value);
}
</script>

<template>
  <PageHeader title="Phân quyền" subtitle="Nhóm quyền quyết định cán bộ được làm gì với từng loại dữ liệu và được dùng chức năng nào. Gán nhóm cho người dùng ở màn hình Người dùng.">
    <RouterLink class="btn" to="/quan-tri/nguoi-dung"><Icon name="users" :size="16" /> Người dùng</RouterLink>
    <button class="btn btn-primary" type="button" @click="startCreate()"><Icon name="plus" :size="16" /> Thêm nhóm quyền</button>
  </PageHeader>

  <p v-if="error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>
  <div v-if="loading" class="grid gap-4 lg:grid-cols-[16rem_1fr]"><div class="card h-64 animate-pulse bg-surface-muted"></div><div class="card h-96 animate-pulse bg-surface-muted"></div></div>

  <div v-else class="grid items-start gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
    <nav class="card p-2" aria-label="Các nhóm quyền">
      <button
        v-for="g in groups"
        :key="g.role"
        type="button"
        class="flex w-full items-start justify-between gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-surface-muted"
        :class="{ 'bg-primary-soft font-semibold': g.role === group?.role }"
        :aria-current="g.role === group?.role ? 'true' : undefined"
        @click="choose(g.role)"
      >
        <span class="min-w-0">
          <span class="block truncate">{{ g.label }}</span>
          <span class="block text-xs font-normal text-ink-muted">{{ g.is_admin ? "Mọi quyền" : g.is_builtin ? "Nhóm có sẵn" : "Nhóm tự tạo" }}</span>
        </span>
        <span class="badge badge-muted shrink-0" :title="`${g.members} người dùng`">{{ g.members }}</span>
      </button>
    </nav>

    <EmptyState v-if="!group" icon="shield-check" title="Chọn một nhóm quyền" text="Chọn nhóm ở bên trái để xem và sửa quyền." />
    <section v-else class="card min-w-0">
      <header class="space-y-3 border-b border-line px-4 py-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <h2 class="m-0 text-lg font-semibold">{{ group.label }}</h2>
          <div class="flex flex-wrap gap-2">
            <button class="btn" type="button" @click="startCreate(group.role)"><Icon name="copy" :size="16" /> Nhân bản</button>
            <button v-if="group.is_builtin && !group.is_admin" class="btn" type="button" @click="confirm = 'reset'"><Icon name="undo" :size="16" /> Khôi phục mặc định</button>
            <button v-if="!group.is_builtin" class="btn text-danger" type="button" @click="confirm = 'remove'"><Icon name="trash-2" :size="16" /> Xóa</button>
            <button v-if="!locked" class="btn btn-primary" type="button" :disabled="!dirty || saving" @click="confirm = 'save'"><Icon :name="saving ? 'loader' : 'save'" :size="16" :spin="saving" /> Lưu thay đổi</button>
          </div>
        </div>
        <p v-if="locked" class="m-0 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning" role="status">Quản trị viên luôn có mọi quyền, mọi chức năng và mọi phông. Nhóm này không sửa được.</p>
        <div v-else class="grid gap-3 sm:grid-cols-[1fr_10rem]">
          <label class="block text-sm"><span class="label">Tên nhóm quyền</span><input v-model="form.label" class="input" type="text" /></label>
          <label class="block text-sm"><span class="label">Loại</span><select v-model="form.group" class="input"><option>Tác nghiệp</option><option>Quản trị</option></select></label>
          <label class="block text-sm sm:col-span-2"><span class="label">Mô tả</span><textarea v-model="form.description" class="input" rows="2"></textarea></label>
        </div>
      </header>

      <div class="flex gap-1 overflow-x-auto border-b border-line px-2" role="tablist" aria-label="Nội dung nhóm quyền">
        <button
          v-for="[key, label, icon] in TABS"
          :id="`tab-${key}`"
          :key="key"
          type="button"
          role="tab"
          class="-mb-px flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium"
          :class="tab === key ? 'border-primary text-primary' : 'border-transparent text-ink-muted hover:text-ink'"
          :aria-selected="tab === key"
          :aria-controls="`panel-${key}`"
          @click="tab = key"
        >
          <Icon :name="icon" :size="16" /> {{ label }}<span v-if="key === 'members'" class="badge badge-muted">{{ group.member_count }}</span>
        </button>
      </div>

      <div v-show="tab === 'data'" id="panel-data" role="tabpanel" aria-labelledby="tab-data" class="space-y-5 p-4">
        <p class="m-0 text-sm text-ink-muted">Đánh dấu một quyền bất kỳ thì tự có quyền Xem; bỏ Xem thì mất mọi quyền trên loại dữ liệu đó. "Chỉ của mình": quyền chỉ áp dụng cho bản ghi do chính người đó tạo. "Trường nhạy cảm": được sửa các trường được bảo vệ (ví dụ nhóm và mức mật của độc giả).</p>
        <div v-for="section in group.matrix" :key="section.section">
          <h3 class="m-0 mb-2 text-sm font-semibold">{{ section.section }}</h3>
          <div class="table-wrap rounded-md border border-line">
            <table class="data-table">
              <caption class="sr-only">Quyền của {{ group.label }} — {{ section.section }}</caption>
              <thead>
                <tr><th scope="col">Loại dữ liệu</th><th v-for="col in sectionColumns(section)" :key="col" scope="col" class="whitespace-nowrap text-center text-xs">{{ group.columns[col] }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in section.rows" :key="row.doctype">
                  <th scope="row" class="text-left font-medium">{{ row.label }}</th>
                  <td v-for="col in sectionColumns(section)" :key="col" class="text-center">
                    <input
                      v-if="row.columns.includes(col)"
                      type="checkbox"
                      class="h-4 w-4 accent-[var(--dm-primary)]"
                      :checked="Boolean(matrix[row.doctype]?.[col])"
                      :disabled="locked"
                      :aria-label="`${row.label}: ${group.columns[col]}`"
                      @change="toggle(row.doctype, col, $event.target.checked)"
                    />
                    <span v-else class="text-ink-subtle" aria-hidden="true">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-show="tab === 'functions'" id="panel-functions" role="tabpanel" aria-labelledby="tab-functions" class="grid gap-4 p-4 md:grid-cols-2">
        <fieldset v-for="m in group.capabilities" :key="m.module" class="m-0 space-y-2 rounded-md border border-line p-3" :disabled="locked">
          <legend class="px-1 text-sm font-semibold">{{ m.module }}</legend>
          <label v-for="item in m.items" :key="item.code" class="flex cursor-pointer items-start gap-2 text-sm">
            <input type="checkbox" class="mt-0.5 h-4 w-4 accent-[var(--dm-primary)]" :checked="capabilities.includes(item.code)" @change="capabilities = toggleValue(capabilities, item.code)" />
            <span>{{ item.label }}</span>
          </label>
        </fieldset>
      </div>

      <div v-show="tab === 'members'" id="panel-members" role="tabpanel" aria-labelledby="tab-members" class="p-4">
        <EmptyState v-if="!group.members.length" icon="users" title="Chưa có ai thuộc nhóm này" text="Gán nhóm quyền cho người dùng ở màn hình Người dùng." />
        <ul v-else class="m-0 list-none space-y-1 p-0 text-sm">
          <li v-for="m in group.members" :key="m.name" class="flex flex-wrap items-center gap-2">
            <span class="font-medium">{{ m.full_name || m.name }}</span><span class="text-xs text-ink-muted">{{ m.name }}</span>
            <span v-if="!m.enabled" class="badge badge-muted">Đã khóa</span>
          </li>
        </ul>
        <RouterLink class="mt-3 inline-block text-sm text-primary hover:underline" :to="{ path: '/quan-tri/nguoi-dung', query: { role: group.role } }">Quản lý người dùng của nhóm này</RouterLink>
      </div>
    </section>
  </div>

  <ConfirmDialog :open="confirm === 'save'" title="Lưu thay đổi nhóm quyền?" confirm-text="Lưu" :busy="saving" @confirm="save" @cancel="confirm = ''">
    <template #default>
      <ul class="m-0 list-disc space-y-1 pl-5 text-sm">
        <li v-if="detailsChanged">Đổi tên, mô tả hoặc loại nhóm</li>
        <li v-for="line in changes" :key="line">{{ line }}</li>
      </ul>
      <p class="mb-0 mt-2 text-xs text-ink-muted">Thay đổi áp dụng ngay cho mọi người dùng thuộc nhóm ({{ group?.member_count || 0 }} người).</p>
    </template>
  </ConfirmDialog>
  <ConfirmDialog :open="confirm === 'remove'" danger title="Xóa nhóm quyền?" confirm-text="Xóa" message="Chỉ xóa được nhóm không còn ai thuộc về; quyền của nhóm bị xóa cùng." @confirm="remove" @cancel="confirm = ''" />
  <ConfirmDialog :open="confirm === 'reset'" title="Khôi phục quyền mặc định?" confirm-text="Khôi phục" message="Quyền trên dữ liệu và chức năng của nhóm trở về như khi cài đặt; các thay đổi đã lưu của nhóm này bị bỏ." @confirm="reset" @cancel="confirm = ''" />
  <ConfirmDialog :open="confirm === 'leave'" title="Bỏ thay đổi chưa lưu?" confirm-text="Bỏ thay đổi" message="Nhóm quyền đang mở có thay đổi chưa lưu." @confirm="leave" @cancel="confirm = ''" />

  <Drawer :open="Boolean(creating)" :title="creating?.copy_from ? 'Nhân bản nhóm quyền' : 'Thêm nhóm quyền'" width="480px" @close="creating = null">
    <form v-if="creating" class="space-y-4" @submit.prevent="create">
      <p v-if="createError" class="whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ createError }}</p>
      <label class="block text-sm"><span class="label">Tên nhóm quyền<span class="text-danger"> *</span></span><input v-model="creating.label" class="input" type="text" maxlength="60" /></label>
      <label class="block text-sm"><span class="label">Mô tả</span><textarea v-model="creating.description" class="input" rows="2"></textarea></label>
      <label class="block text-sm"><span class="label">Loại</span><select v-model="creating.group" class="input"><option>Tác nghiệp</option><option>Quản trị</option></select></label>
      <label class="block text-sm"><span class="label">Bắt đầu từ quyền của nhóm</span>
        <select v-model="creating.copy_from" class="input"><option value="">Không có quyền nào</option><option v-for="g in groups" :key="g.role" :value="g.role">{{ g.label }}</option></select></label>
    </form>
    <template #footer>
      <button class="btn" type="button" @click="creating = null">Hủy</button>
      <button class="btn btn-primary" type="button" :disabled="!creating?.label?.trim()" @click="create"><Icon name="plus" :size="16" /> Tạo</button>
    </template>
  </Drawer>
</template>
