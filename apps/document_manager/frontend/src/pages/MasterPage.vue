<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import { boot, masterBySlug } from "../lib/boot.js";
import { describe } from "../lib/doctype.js";
import { pageTitle } from "../lib/page.js";
import MasterList from "./MasterList.vue";
import MasterTree from "./MasterTree.vue";
import NotFound from "./NotFound.vue";
import SettingsPage from "./SettingsPage.vue";

// One page for every registered screen of a section (the route says which: catalogues, readers): a flat list,
// a tree, or - for a single DocType such as the reader settings - one form.
const route = useRoute();
const sources = computed(() => (route.meta.sources || ["masters"]));
const master = computed(() => sources.value.map((source) => masterBySlug(route.params.slug || route.meta.slug, source)).find(Boolean) || null);
const meta = ref(null);
const error = ref("");
const loading = ref(false);

watch(
  master,
  async (current) => {
    meta.value = null;
    error.value = "";
    if (!current) return;
    pageTitle.value = current.label;
    loading.value = true;
    try {
      meta.value = await describe(current.doctype);
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);
void boot;
</script>

<template>
  <NotFound v-if="!master" />
  <div v-else-if="loading" class="flex items-center gap-2 py-10 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
  <EmptyState v-else-if="error" icon="alert-triangle" title="Không mở được danh mục" :text="error" />
  <!-- :key makes switching between two catalogues build a fresh page instead of reusing state -->
  <SettingsPage v-else-if="meta && meta.is_single" :key="meta.doctype" :meta="meta" />
  <MasterTree v-else-if="meta && meta.is_tree" :key="meta.doctype" :meta="meta" :master="master" />
  <MasterList v-else-if="meta" :key="meta.doctype" :meta="meta" />
</template>
