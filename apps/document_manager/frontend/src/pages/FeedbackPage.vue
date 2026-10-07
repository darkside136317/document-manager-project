<script setup>
import { onBeforeUnmount, onMounted, reactive } from "vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { debounce, formatDate, formatDateTime } from "../lib/format.js";
import { refreshBadges } from "../lib/registrations.js";
import { toast, toastError } from "../lib/toast.js";

// Feedback (góp ý) the readers sent: read it, mark it seen, answer. The answer reaches the reader as a notification.
const PAGE_SIZE = 20;
const FILTERS = [{ value: "Mới", label: "Chưa xem" }, { value: "Đã xem", label: "Đã xem" }, { value: "Đã phản hồi", label: "Đã phản hồi" }, { value: "", label: "Tất cả" }];
const state = reactive({ rows: [], total: 0, counts: {}, page: 1, status: "Mới", search: "", loading: true, error: "" });
const drawer = reactive({ open: false, item: null, reply: "", busy: false, error: "" });
let ticket = 0;

async function load() {
  const mine = ++ticket;
  state.loading = true;
  state.error = "";
  try {
    const result = await api.feedback.list({ status: state.status, search: state.search, page: state.page, page_size: PAGE_SIZE });
    if (mine !== ticket) return;
    Object.assign(state, { rows: result.rows, total: result.total, counts: result.counts });
  } catch (e) {
    if (mine === ticket) state.error = e.message;
  } finally {
    if (mine === ticket) state.loading = false;
  }
}
const searchSoon = debounce(() => { state.page = 1; load(); }, 300);
onMounted(load);
onBeforeUnmount(() => searchSoon.cancel());

function setStatus(value) { state.status = value; state.page = 1; load(); }

async function open(row) {
  Object.assign(drawer, { open: true, item: null, reply: "", busy: false, error: "" });
  try {
    let item = await api.feedback.get(row.name);
    if (item.status === "Mới" && item.actions.includes("Đánh dấu đã xem")) {
      await api.requests.action("Reader Feedback", item.name, "Đánh dấu đã xem");
      item = await api.feedback.get(row.name);
      load();
      refreshBadges(api.slips.badges);
    }
    drawer.item = item;
  } catch (e) {
    drawer.error = e.message;
  }
}
const close = () => { drawer.open = false; };

async function send() {
  if (!drawer.reply.trim()) return (drawer.error = "Hãy nhập nội dung phản hồi.");
  drawer.busy = true;
  drawer.error = "";
  try {
    await api.requests.action("Reader Feedback", drawer.item.name, "Phản hồi", drawer.reply.trim());
    toast("Đã gửi phản hồi cho độc giả");
    drawer.item = await api.feedback.get(drawer.item.name);
    load();
    refreshBadges(api.slips.badges);
  } catch (e) {
    drawer.error = e.message;
    toastError(e.message);
  } finally {
    drawer.busy = false;
  }
}
</script>

<template>
  <PageHeader title="Góp ý của độc giả" subtitle="Ý kiến độc giả gửi từ cổng khai thác tài liệu.">
    <div class="relative">
      <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" />
      <input v-model="state.search" class="input w-64 pl-9" type="search" placeholder="Tìm tiêu đề, độc giả..." aria-label="Tìm góp ý" @input="searchSoon" />
    </div>
  </PageHeader>

  <div class="mb-4 flex flex-wrap gap-1" role="group" aria-label="Trạng thái">
    <button v-for="f in FILTERS" :key="f.label" type="button" class="btn btn-sm" :class="{ 'btn-primary': state.status === f.value }" :aria-pressed="state.status === f.value" @click="setStatus(f.value)">
      {{ f.label }}<span v-if="f.value && state.counts[f.value]" class="ml-1 rounded-full bg-surface-muted px-1.5 text-xs text-ink-muted">{{ state.counts[f.value] }}</span>
    </button>
  </div>

  <p v-if="state.error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ state.error }}</p>

  <section class="card overflow-hidden">
    <div v-if="state.loading && !state.rows.length" class="flex items-center gap-2 px-5 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <EmptyState v-else-if="!state.rows.length" icon="message-square" title="Không có góp ý nào" text="Góp ý mới của độc giả sẽ hiện ở đây." />
    <template v-else>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th scope="col">Tiêu đề</th><th scope="col">Độc giả</th><th scope="col">Ngày gửi</th><th scope="col">Trạng thái</th></tr></thead>
          <tbody :class="{ 'opacity-60': state.loading }">
            <tr v-for="row in state.rows" :key="row.name" class="is-clickable" tabindex="0" @click="open(row)" @keydown.enter="open(row)">
              <td class="font-medium">{{ row.subject }}</td>
              <td>{{ row.reader_name || row.reader }}</td>
              <td class="whitespace-nowrap text-ink-soft">{{ formatDate(row.feedback_date) }}</td>
              <td><StatusBadge :value="row.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar :page="state.page" :page-size="PAGE_SIZE" :total="state.total" @change="(p) => { state.page = p; load(); }" />
    </template>
  </section>

  <Drawer :open="drawer.open" :title="drawer.item ? drawer.item.subject : 'Góp ý'" width="560px" @close="close">
    <div v-if="!drawer.item && !drawer.error" class="flex items-center gap-2 py-8 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <template v-if="drawer.item">
      <div class="mb-3 flex items-center justify-between gap-3 text-sm text-ink-muted">
        <span>{{ drawer.item.reader_name || drawer.item.reader }} · {{ formatDate(drawer.item.feedback_date) }}</span>
        <StatusBadge :value="drawer.item.status" />
      </div>
      <div class="rich-view rounded-md bg-surface-muted p-3 text-sm" v-html="drawer.item.content"></div>
      <template v-if="drawer.item.response">
        <h3 class="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-ink-muted">Phản hồi đã gửi</h3>
        <div class="rich-view rounded-md bg-info-soft p-3 text-sm" v-html="drawer.item.response"></div>
        <p class="mt-1 text-xs text-ink-muted">{{ drawer.item.responded_by }} · {{ formatDateTime(drawer.item.responded_date) }}</p>
      </template>
      <div v-else-if="drawer.item.actions.includes('Phản hồi')" class="mt-5">
        <label class="label" for="fb-reply">Phản hồi cho độc giả</label>
        <textarea id="fb-reply" v-model="drawer.reply" class="input" rows="5"></textarea>
      </div>
    </template>
    <p v-if="drawer.error" class="mt-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ drawer.error }}</p>
    <template #footer>
      <button class="btn" type="button" @click="close">Đóng</button>
      <button v-if="drawer.item && !drawer.item.response && drawer.item.actions.includes('Phản hồi')" class="btn btn-primary" type="button" :disabled="drawer.busy" @click="send">
        <Icon :name="drawer.busy ? 'loader' : 'send'" :size="16" :spin="drawer.busy" /> Gửi phản hồi
      </button>
    </template>
  </Drawer>
</template>
