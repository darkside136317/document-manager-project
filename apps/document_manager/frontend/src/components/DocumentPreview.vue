<script setup>
import EmptyState from "./EmptyState.vue";
import Icon from "./Icon.vue";

// What the server says it can show of a document's file (api.file_access.get_preview): the PDF or
// image itself, the extracted text of Office files, or a notice when there is nothing to show.
defineProps({
  preview: { type: Object, default: null },
  attached: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
});
</script>

<template>
  <div class="min-h-[320px]">
    <div v-if="loading" class="flex items-center gap-2 p-8 text-ink-muted"><Icon name="loader" spin /> Đang tải bản xem trước...</div>
    <EmptyState v-else-if="!attached" icon="file" title="Văn bản chưa có tệp" text="Tải một tệp lên để xem trước và tìm kiếm theo nội dung." />
    <EmptyState v-else-if="error" icon="alert-triangle" title="Không xem trước được" :text="error" />
    <template v-else-if="preview">
      <iframe
        v-if="preview.kind === 'inline' && preview.file_type === 'PDF'"
        class="h-[72vh] w-full rounded-md border border-line bg-surface-muted"
        :src="preview.preview_url"
        :title="`Xem trước ${preview.title}`"
      ></iframe>
      <img
        v-else-if="preview.kind === 'inline'"
        class="max-h-[72vh] max-w-full rounded-md border border-line object-contain"
        :src="preview.preview_url"
        :alt="preview.title"
      />
      <div v-else-if="preview.kind === 'text'">
        <p class="mb-2 text-sm text-ink-muted">{{ preview.notice }}</p>
        <pre class="m-0 max-h-[68vh] overflow-auto whitespace-pre-wrap rounded-md border border-line bg-surface-muted p-4 text-sm">{{ preview.content }}</pre>
      </div>
      <EmptyState v-else icon="file" title="Chưa xem trước được định dạng này" :text="preview.notice" />
    </template>
  </div>
</template>
