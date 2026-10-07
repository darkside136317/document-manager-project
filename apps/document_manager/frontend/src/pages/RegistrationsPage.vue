<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import OneTimeLinkDialog from "../components/OneTimeLinkDialog.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import ReasonDialog from "../components/ReasonDialog.vue";
import { api } from "../lib/api.js";
import { debounce, formatDateTime } from "../lib/format.js";
import { absoluteLink, describeRequest, isResetRequest, registrationTone, setPendingBadge, STATUS_FILTERS, TYPE_FILTERS } from "../lib/registrations.js";
import { toast } from "../lib/toast.js";

// Queue of sign-up and forgotten-password requests from the reader site. Approving creates the
// account (or picks a new password) and shows the one-time link once, for the officer to pass on.
const PAGE_SIZE = 20;
const state = reactive({ rows: [], total: 0, page: 1, status: "Mới", type: "", search: "", loading: true, error: "" });
const groups = ref([]);
const drawer = reactive({ open: false, row: null, group: "", busy: false, error: "" });
const rejecting = reactive({ open: false, busy: false, error: "" });
const link = reactive({ open: false, url: "", user: "" });
let ticket = 0;

async function load() {
  const mine = ++ticket;
  state.loading = true;
  state.error = "";
  try {
    const result = await api.registrations.list({
      status: state.status, request_type: state.type, search: state.search,
      start: (state.page - 1) * PAGE_SIZE, page_length: PAGE_SIZE,
    });
    if (mine !== ticket) return;
    state.rows = result.rows;
    state.total = result.total;
  } catch (e) {
    if (mine === ticket) state.error = e.message;
  } finally {
    if (mine === ticket) state.loading = false;
  }
}

async function refreshBadge() {
  try {
    setPendingBadge(await api.registrations.pending());
  } catch {
    /* the sidebar counter is a convenience */
  }
}

const searchSoon = debounce(() => { state.page = 1; load(); }, 300);
onMounted(async () => {
  load();
  try {
    groups.value = await api.registrations.groups();
  } catch {
    groups.value = [];
  }
});
onBeforeUnmount(() => searchSoon.cancel());

function setStatus(value) { state.status = value; state.page = 1; load(); }
function setType() { state.page = 1; load(); }

function openRow(row) {
  Object.assign(drawer, { open: true, row, group: groups.value.find((g) => g.is_default)?.name || "", busy: false, error: "" });
}
const closeDrawer = () => { drawer.open = false; };

async function approve() {
  drawer.busy = true;
  drawer.error = "";
  try {
    const row = drawer.row;
    const result = await api.registrations.approve(row.name, isResetRequest(row) ? null : drawer.group || null);
    showLink(result);
    closeDrawer();
    toast(isResetRequest(row) ? "Đã cấp liên kết đặt mật khẩu." : "Đã tạo tài khoản độc giả.");
    await Promise.all([load(), refreshBadge()]);
  } catch (e) {
    drawer.error = e.message;
  } finally {
    drawer.busy = false;
  }
}

function askReject() { Object.assign(rejecting, { open: true, busy: false, error: "" }); }
async function reject(reason) {
  rejecting.busy = true;
  rejecting.error = "";
  try {
    await api.registrations.reject(drawer.row.name, reason);
    rejecting.open = false;
    closeDrawer();
    toast("Đã từ chối yêu cầu.");
    await Promise.all([load(), refreshBadge()]);
  } catch (e) {
    rejecting.error = e.message;
  } finally {
    rejecting.busy = false;
  }
}

async function reissue() {
  drawer.busy = true;
  drawer.error = "";
  try {
    showLink(await api.registrations.reissue(drawer.row.name));
    closeDrawer();
  } catch (e) {
    drawer.error = e.message;
  } finally {
    drawer.busy = false;
  }
}

function showLink(result) {
  Object.assign(link, { open: true, url: absoluteLink(result.set_password_path), user: result.user });
}
</script>

<template>
  <PageHeader title="Đăng ký độc giả" subtitle="Yêu cầu đăng ký tài khoản và cấp lại mật khẩu gửi từ cổng độc giả.">
    <div class="relative">
      <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
      <input v-model="state.search" class="input w-64 pl-9" type="search" placeholder="Tìm theo tên, email, đơn vị..." aria-label="Tìm kiếm" @input="searchSoon" />
    </div>
  </PageHeader>

  <div class="mb-4 flex flex-wrap items-center gap-2">
    <div class="flex flex-wrap gap-1" role="group" aria-label="Trạng thái">
      <button
        v-for="option in STATUS_FILTERS" :key="option.label" type="button" class="btn btn-sm"
        :class="{ 'btn-primary': state.status === option.value }" :aria-pressed="state.status === option.value" @click="setStatus(option.value)"
      >{{ option.label }}</button>
    </div>
    <select v-model="state.type" class="input w-auto" aria-label="Loại yêu cầu" @change="setType">
      <option v-for="option in TYPE_FILTERS" :key="option.label" :value="option.value">{{ option.label }}</option>
    </select>
  </div>

  <p v-if="state.error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ state.error }}</p>

  <section class="card overflow-hidden">
    <div v-if="state.loading && !state.rows.length" class="flex items-center gap-2 px-5 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <EmptyState v-else-if="!state.rows.length" icon="user-plus" :title="state.status === 'Mới' ? 'Không có yêu cầu nào đang chờ' : 'Không có yêu cầu phù hợp'" text="Yêu cầu mới từ cổng độc giả sẽ hiện ở đây." />
    <template v-else>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">Người gửi</th><th scope="col">Loại yêu cầu</th><th scope="col">Cơ quan, đơn vị</th>
              <th scope="col">Gửi lúc</th><th scope="col">Trạng thái</th><th scope="col" class="w-12"><span class="sr-only">Mở</span></th>
            </tr>
          </thead>
          <tbody :class="{ 'opacity-60': state.loading }">
            <tr v-for="row in state.rows" :key="row.name" class="is-clickable" tabindex="0" @click="openRow(row)" @keydown.enter="openRow(row)">
              <td><div class="font-medium">{{ row.full_name }}</div><div class="text-xs text-ink-muted">{{ row.email }}</div></td>
              <td>{{ row.request_type }}</td>
              <td class="text-ink-soft">{{ [row.organization, row.position].filter(Boolean).join(" — ") }}</td>
              <td class="whitespace-nowrap text-ink-soft">{{ formatDateTime(row.creation) }}</td>
              <td><span :class="`badge badge-${registrationTone(row.status)}`">{{ row.status }}</span></td>
              <td class="text-right text-ink-subtle"><Icon name="chevron-right" :size="16" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar :page="state.page" :page-size="PAGE_SIZE" :total="state.total" @change="(p) => { state.page = p; load(); }" />
    </template>
  </section>

  <Drawer :open="drawer.open" :title="drawer.row ? drawer.row.request_type : ''" width="520px" @close="closeDrawer">
    <template v-if="drawer.row">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div>
          <p class="m-0 text-lg font-semibold">{{ drawer.row.full_name }}</p>
          <p class="m-0 text-sm text-ink-muted">{{ drawer.row.email }}</p>
        </div>
        <span :class="`badge badge-${registrationTone(drawer.row.status)}`">{{ drawer.row.status }}</span>
      </div>
      <dl class="grid grid-cols-[140px_1fr] gap-x-4 gap-y-2 text-sm">
        <template v-for="[label, value] in [
          ['Điện thoại', drawer.row.phone], ['Số CMND/CCCD', drawer.row.id_number], ['Cơ quan, đơn vị', drawer.row.organization],
          ['Chức vụ', drawer.row.position], ['Địa chỉ', drawer.row.address], ['Mục đích khai thác', drawer.row.purpose],
          ['Gửi lúc', formatDateTime(drawer.row.creation)], ['Mã yêu cầu', drawer.row.name],
        ].filter(([, v]) => v)" :key="label">
          <dt class="text-ink-muted">{{ label }}</dt><dd class="m-0 whitespace-pre-line break-words">{{ value }}</dd>
        </template>
        <template v-if="drawer.row.status !== 'Mới'">
          <dt class="text-ink-muted">Xử lý bởi</dt><dd class="m-0">{{ drawer.row.decided_by }} · {{ formatDateTime(drawer.row.decided_on) }}</dd>
          <template v-if="drawer.row.rejection_reason"><dt class="text-ink-muted">Lý do từ chối</dt><dd class="m-0 whitespace-pre-line">{{ drawer.row.rejection_reason }}</dd></template>
          <template v-if="drawer.row.reader"><dt class="text-ink-muted">Hồ sơ độc giả</dt><dd class="m-0"><a :href="`/app/reader/${encodeURIComponent(drawer.row.reader)}`">{{ drawer.row.reader }}</a></dd></template>
        </template>
      </dl>

      <div v-if="drawer.row.status === 'Mới' && !isResetRequest(drawer.row) && groups.length" class="mt-5">
        <label class="label" for="reg-group">Nhóm độc giả</label>
        <select id="reg-group" v-model="drawer.group" class="input">
          <option v-for="g in groups" :key="g.name" :value="g.name">{{ g.name }}{{ g.is_default ? " (mặc định)" : "" }}</option>
        </select>
        <p class="mt-1 text-xs text-ink-muted">Nhóm quyết định phạm vi, mức mật và chức năng độc giả được dùng.</p>
      </div>
      <p v-if="drawer.row.status === 'Mới'" class="mt-4 rounded-md bg-info-soft px-3 py-2 text-sm text-ink-soft">
        {{ isResetRequest(drawer.row)
          ? "Duyệt sẽ tạo liên kết đặt mật khẩu mới (mật khẩu cũ vẫn dùng được đến khi người dùng đặt mật khẩu mới)."
          : "Duyệt sẽ tạo tài khoản độc giả và một liên kết đặt mật khẩu dùng một lần. Hệ thống không gửi email: hãy chuyển liên kết cho người đăng ký." }}
      </p>
      <p v-if="drawer.error" class="mt-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ drawer.error }}</p>
    </template>
    <template #footer>
      <template v-if="drawer.row?.status === 'Mới'">
        <button class="btn btn-danger" type="button" :disabled="drawer.busy" @click="askReject"><Icon name="x" :size="16" /> Từ chối</button>
        <button class="btn btn-primary" type="button" :disabled="drawer.busy" @click="approve">
          <Icon :name="drawer.busy ? 'loader' : 'check'" :size="16" :spin="drawer.busy" /> Duyệt
        </button>
      </template>
      <button v-else-if="drawer.row?.status === 'Đã duyệt'" class="btn" type="button" :disabled="drawer.busy" @click="reissue">
        <Icon name="key-round" :size="16" /> Cấp lại liên kết đặt mật khẩu
      </button>
    </template>
  </Drawer>

  <ReasonDialog
    :open="rejecting.open" title="Từ chối yêu cầu" label="Lý do từ chối" confirm-text="Từ chối" danger :busy="rejecting.busy" :error="rejecting.error"
    :message="drawer.row ? `${describeRequest(drawer.row)}
Nhập lý do để người dùng được biết khi liên hệ lại.` : ''"
    @confirm="reject" @cancel="rejecting.open = false"
  />
  <OneTimeLinkDialog :open="link.open" :url="link.url" :user="link.user" @close="link.open = false" />
</template>
