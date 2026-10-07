<script setup>
import { computed, reactive, ref } from "vue";
import { api } from "../lib/api.js";
import { formatSize, processQueue, validateFile } from "../lib/upload.js";
import Icon from "./Icon.vue";

// Pick or drop files, upload them with a progress bar each, and turn every file into a document of
// `archivalFile` (mode "create") or replace the file of `document` (mode "replace").
const props = defineProps({
  rules: { type: Object, required: true }, // {extensions, max_mb}
  mode: { type: String, default: "create" },
  archivalFile: { type: String, default: "" },
  document: { type: String, default: "" },
});
const emit = defineEmits(["done"]);

const items = reactive([]);
const dragging = ref(false);
const running = ref(false);
const input = ref(null);
const single = computed(() => props.mode === "replace");

function add(fileList) {
  const files = [...fileList];
  if (single.value) items.splice(0, items.length);
  for (const file of single.value ? files.slice(0, 1) : files) {
    const error = validateFile(file, props.rules);
    items.push({ id: `${file.name}-${file.size}-${items.length}`, file, status: error ? "error" : "waiting", progress: 0, error, document: null });
  }
}
function onDrop(event) {
  dragging.value = false;
  add(event.dataTransfer.files);
}
function onPick(event) {
  add(event.target.files);
  event.target.value = "";
}

const waiting = computed(() => items.filter((i) => i.status === "waiting").length);
const finished = computed(() => items.filter((i) => i.status === "done").length);
const failed = computed(() => items.filter((i) => i.status === "error").length);

async function start() {
  running.value = true;
  const create = (fileUrl) =>
    single.value ? api.archive.attachFile(props.document, fileUrl) : api.archive.addDocument(props.archivalFile, fileUrl);
  try {
    await processQueue(items, { rules: props.rules, create });
  } finally {
    running.value = false;
    if (items.some((i) => i.status === "done")) emit("done", items.filter((i) => i.status === "done"));
  }
}
function retry(item) {
  Object.assign(item, { status: "waiting", error: "", progress: 0 });
}
function remove(item) {
  items.splice(items.indexOf(item), 1);
}
const statusText = { waiting: "Chờ tải lên", uploading: "Đang tải lên", saving: "Đang tạo văn bản", done: "Hoàn tất", error: "Lỗi" };
defineExpose({ items });
</script>

<template>
  <div>
    <div
      class="grid cursor-pointer place-items-center gap-1 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors"
      :class="dragging ? 'border-primary bg-primary-soft' : 'border-line-strong bg-surface-muted'"
      role="button"
      tabindex="0"
      :aria-label="single ? 'Chọn tệp thay thế' : 'Chọn tệp để tải lên'"
      @click="input.click()"
      @keydown.enter="input.click()"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <Icon name="upload" :size="28" class="text-ink-muted" />
      <p class="m-0 text-sm font-medium">{{ single ? "Kéo thả tệp thay thế vào đây" : "Kéo thả tệp vào đây, hoặc bấm để chọn" }}</p>
      <p class="m-0 text-xs text-ink-muted">
        {{ rules.extensions.join(", ") }} · tối đa {{ rules.max_mb }} MB mỗi tệp{{ single ? "" : " · mỗi tệp thành một văn bản" }}
      </p>
      <input ref="input" class="hidden" type="file" :multiple="!single" :accept="rules.extensions.map((e) => '.' + e).join(',')" @change="onPick" />
    </div>

    <ul v-if="items.length" class="m-0 mt-4 list-none space-y-2 p-0">
      <li v-for="item in items" :key="item.id" class="rounded-md border border-line px-3 py-2">
        <div class="flex items-center gap-3">
          <Icon :name="item.status === 'done' ? 'circle-check' : item.status === 'error' ? 'alert-triangle' : 'file-text'" :size="18"
                :class="item.status === 'done' ? 'text-success' : item.status === 'error' ? 'text-danger' : 'text-ink-muted'" />
          <div class="min-w-0 flex-1">
            <p class="m-0 truncate text-sm font-medium">{{ item.file.name }}</p>
            <p class="m-0 text-xs text-ink-muted">{{ formatSize(item.file.size) }} · {{ statusText[item.status] }}<template v-if="item.status === 'uploading'"> {{ item.progress }}%</template></p>
          </div>
          <RouterLink v-if="item.document && !single" class="text-xs" :to="`/van-ban/${encodeURIComponent(item.document.name)}`">Mở</RouterLink>
          <button v-if="item.status === 'error' && !validateFile(item.file, rules)" class="btn btn-ghost !min-h-0 !px-2 !py-1 text-xs" type="button" @click="retry(item)">Thử lại</button>
          <button v-if="!['uploading', 'saving'].includes(item.status)" class="btn btn-ghost btn-icon !min-h-0 !p-1" type="button" aria-label="Bỏ tệp" @click="remove(item)"><Icon name="x" :size="14" /></button>
        </div>
        <div v-if="['uploading', 'saving'].includes(item.status)" class="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-muted" role="progressbar" :aria-valuenow="item.progress" aria-valuemin="0" aria-valuemax="100">
          <div class="h-full bg-primary transition-all" :style="{ width: `${item.status === 'saving' ? 100 : item.progress}%` }"></div>
        </div>
        <p v-if="item.error" class="m-0 mt-1 whitespace-pre-line text-xs text-danger" role="alert">{{ item.error }}</p>
      </li>
    </ul>

    <div class="mt-4 flex flex-wrap items-center justify-between gap-2">
      <p class="m-0 text-sm text-ink-muted">
        <template v-if="items.length">{{ finished }}/{{ items.length }} hoàn tất<template v-if="failed"> · {{ failed }} lỗi</template></template>
      </p>
      <button class="btn btn-primary" type="button" :disabled="running || !waiting" @click="start">
        <Icon :name="running ? 'loader' : 'upload'" :size="16" :spin="running" />
        {{ running ? "Đang tải lên..." : single ? "Thay tệp" : `Tải lên${waiting ? ` ${waiting} tệp` : ""}` }}
      </button>
    </div>
  </div>
</template>
