<script setup>
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Drawer from "../components/Drawer.vue";
import EmptyState from "../components/EmptyState.vue";
import ExportPanel from "../components/ExportPanel.vue";
import Icon from "../components/Icon.vue";
import ImportPanel from "../components/ImportPanel.vue";
import JobCard from "../components/JobCard.vue";
import PageHeader from "../components/PageHeader.vue";
import PaginationBar from "../components/PaginationBar.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../lib/api.js";
import { formatDateTime } from "../lib/format.js";

// Exchange of archival data as XML (module 5): export, import and the history of both.
const route = useRoute();
const router = useRouter();
const TABS = [["xuat", "Xuất XML", "file-down"], ["nhap", "Nhập XML", "upload"], ["lich-su", "Lịch sử", "history"]];

const caps = ref(null);
const error = ref("");
const tab = ref(TABS.some(([key]) => key === route.query.tab) ? route.query.tab : "xuat");

const history = ref({ data: [], total: 0, page: 1, page_size: 15 });
const loadingHistory = ref(false);
const detail = ref(null);
const removing = ref(null);
const removeError = ref("");

async function loadHistory(page = 1) {
  loadingHistory.value = true;
  try {
    history.value = await api.exchange.jobs({ page, page_size: 15 });
  } catch (e) {
    error.value = e.message;
  } finally {
    loadingHistory.value = false;
  }
}

async function openDetail(job) {
  try {
    detail.value = await api.exchange.job(job.name);
  } catch (e) {
    error.value = e.message;
  }
}

async function remove() {
  removeError.value = "";
  try {
    await api.exchange.remove(removing.value.name);
    removing.value = null;
    detail.value = null;
    await loadHistory(history.value.page);
  } catch (e) {
    removeError.value = e.message;
  }
}

onMounted(async () => {
  try {
    caps.value = await api.exchange.capabilities();
  } catch (e) {
    error.value = e.message;
  }
  if (tab.value === "lich-su") loadHistory();
});
watch(tab, (value) => {
  router.replace({ query: { tab: value } });
  if (value === "lich-su") loadHistory();
});
const levelLabel = (doctype) => caps.value?.levels.find((l) => l.doctype === doctype)?.label || doctype || "";
</script>

<template>
  <PageHeader title="Xuất, nhập dữ liệu XML" subtitle="Trao đổi dữ liệu lưu trữ với hệ thống khác, sao lưu hoặc chuyển đổi: xuất kết quả tìm kiếm ra XML, nhập XML vào cơ sở dữ liệu.">
    <a class="btn" href="/api/method/document_manager.document_manager.api.exchange.download_schema"><Icon name="file-code" :size="16" /> Lược đồ XSD</a>
  </PageHeader>

  <EmptyState v-if="error && !caps" icon="alert-triangle" title="Không mở được chức năng trao đổi dữ liệu" :text="error" />

  <template v-else-if="caps">
    <div class="mb-5 flex gap-1 border-b border-line" role="tablist" aria-label="Trao đổi dữ liệu">
      <button
        v-for="[key, label, icon] in TABS"
        :id="`tab-${key}`"
        :key="key"
        type="button"
        role="tab"
        class="-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium"
        :class="tab === key ? 'border-primary text-primary' : 'border-transparent text-ink-muted hover:text-ink'"
        :aria-selected="tab === key"
        :aria-controls="`panel-${key}`"
        @click="tab = key"
      ><Icon :name="icon" :size="16" /> {{ label }}</button>
    </div>

    <p v-if="error" class="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

    <div v-show="tab === 'xuat'" id="panel-xuat" role="tabpanel" aria-labelledby="tab-xuat"><ExportPanel :caps="caps" @finished="loadHistory()" /></div>
    <div v-show="tab === 'nhap'" id="panel-nhap" role="tabpanel" aria-labelledby="tab-nhap"><ImportPanel :caps="caps" @finished="loadHistory()" /></div>

    <section v-show="tab === 'lich-su'" id="panel-lich-su" class="card" role="tabpanel" aria-labelledby="tab-lich-su">
      <EmptyState v-if="!loadingHistory && !history.data.length" icon="history" title="Chưa có lượt xuất, nhập nào" text="Các lượt xuất và nhập XML sẽ được ghi lại ở đây." />
      <div v-else class="table-wrap" :class="{ 'opacity-60': loadingHistory }">
        <table class="data-table">
          <caption class="sr-only">Lịch sử xuất, nhập XML</caption>
          <thead><tr><th scope="col">Lúc</th><th scope="col">Chiều</th><th scope="col">Cấp</th><th scope="col">Tệp</th><th scope="col">Tình trạng</th><th scope="col">Kết quả</th><th scope="col">Người thực hiện</th></tr></thead>
          <tbody>
            <tr v-for="job in history.data" :key="job.name" class="is-clickable" tabindex="0" @click="openDetail(job)" @keydown.enter="openDetail(job)">
              <td class="whitespace-nowrap">{{ formatDateTime(job.creation) }}</td>
              <td>{{ job.direction }}<span v-if="job.dry_run" class="badge badge-info ml-1">thử</span></td>
              <td>{{ levelLabel(job.level) }}</td>
              <td class="max-w-[14rem] truncate font-medium">{{ job.file_name }}</td>
              <td><StatusBadge :value="job.status" /></td>
              <td class="max-w-md truncate text-ink-soft" :title="job.summary">{{ job.summary }}</td>
              <td class="text-ink-muted">{{ job.owner }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationBar v-if="history.total" :page="history.page" :page-size="history.page_size" :total="history.total" @change="loadHistory" />
    </section>
  </template>

  <Drawer :open="Boolean(detail)" :title="detail ? `${detail.direction} XML ${detail.name}` : ''" width="760px" @close="detail = null">
    <JobCard v-if="detail" :job="detail" :levels="caps.levels" @cancel="api.exchange.cancel($event.name).then(() => openDetail($event))">
      <button v-if="!detail.busy" class="btn text-danger" type="button" @click="removing = detail"><Icon name="trash-2" :size="16" /> Xóa lượt này</button>
    </JobCard>
  </Drawer>
  <ConfirmDialog
    :open="Boolean(removing)" danger title="Xóa lượt trao đổi?" confirm-text="Xóa" :error="removeError"
    message="Lượt trao đổi và tệp XML của nó sẽ bị xóa. Dữ liệu đã nhập vào hệ thống không bị ảnh hưởng."
    @confirm="remove" @cancel="removing = null"
  />
</template>
