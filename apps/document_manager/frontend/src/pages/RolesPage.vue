<script setup>
import { onMounted, ref } from "vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { api } from "../lib/api.js";
import { permissionIcons, permissionText } from "../lib/admin.js";

// What each staff role may do on the DocTypes of the app (read from the permissions the server really enforces).
const matrix = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    matrix.value = await api.users.matrix();
  } catch (e) {
    error.value = e.message;
  }
});
</script>

<template>
  <PageHeader title="Phân quyền vai trò" subtitle="Mỗi người dùng được cấp một hoặc nhiều vai trò; bảng dưới cho biết mỗi vai trò làm được gì với từng loại dữ liệu.">
    <RouterLink class="btn" to="/quan-tri/nguoi-dung"><Icon name="users" :size="16" /> Gán vai trò cho người dùng</RouterLink>
  </PageHeader>

  <EmptyState v-if="error" icon="alert-triangle" title="Không đọc được phân quyền" :text="error" />
  <template v-else-if="matrix">
    <section class="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Các vai trò">
      <article v-for="role in matrix.roles" :key="role.role" class="card px-4 py-3">
        <h2 class="m-0 flex items-center gap-2 text-base font-semibold">{{ role.label }} <span class="badge badge-muted">{{ role.group }}</span></h2>
        <p class="mb-0 mt-1 text-sm text-ink-soft">{{ role.description }}</p>
      </article>
    </section>

    <section v-for="section in matrix.sections" :key="section.section" class="card mb-5">
      <h2 class="m-0 border-b border-line px-4 py-3 text-sm font-semibold">{{ section.section }}</h2>
      <div class="table-wrap">
        <table class="data-table">
          <caption class="sr-only">Quyền theo vai trò: {{ section.section }}</caption>
          <thead><tr><th scope="col">Loại dữ liệu</th><th v-for="role in matrix.roles" :key="role.role" scope="col" class="text-center">{{ role.label }}</th></tr></thead>
          <tbody>
            <tr v-for="row in section.doctypes" :key="row.doctype">
              <th scope="row" class="text-left font-medium">{{ row.label }}</th>
              <td v-for="role in matrix.roles" :key="role.role" class="text-center text-xs">
                <span class="inline-flex flex-wrap justify-center gap-1" :aria-label="`${role.label}: ${permissionText(row.perms[role.role])}`">
                  <template v-if="permissionText(row.perms[role.role]) !== 'Không'">
                    <span v-for="[key, label] in permissionIcons" :key="key" class="badge" :class="row.perms[role.role][key] ? (key === 'delete' ? 'badge-danger' : key === 'read' ? 'badge-muted' : 'badge-info') : 'opacity-25 badge-muted'">{{ label }}</span>
                  </template>
                  <span v-else class="text-ink-subtle">—</span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <p class="m-0 text-xs text-ink-muted">Quyền tính ở mức DocType; độc giả không có vai trò nào ở đây (họ chỉ dùng trang độc giả và chỉ thấy tài liệu theo nhóm quyền của mình). Quyền đọc theo mức độ mật và theo phông áp dụng thêm cho độc giả.</p>
  </template>
</template>
