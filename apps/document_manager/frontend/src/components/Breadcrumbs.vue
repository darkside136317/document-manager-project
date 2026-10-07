<script setup>
import Icon from "./Icon.vue";

// Fonds › Record group › Catalog › File. Every crumb opens the cataloguing browser at that node.
defineProps({ items: { type: Array, default: () => [] } });
const link = (item) => {
  if (item.doctype === "Archival File") return `/ho-so/${encodeURIComponent(item.name)}`;
  return { path: "/bien-muc", query: { node: `${item.doctype}:${item.name}` } };
};
</script>

<template>
  <nav v-if="items.length" aria-label="Vị trí" class="mb-2 flex flex-wrap items-center gap-1 text-sm text-ink-muted">
    <RouterLink to="/bien-muc" class="hover:underline">Biên mục</RouterLink>
    <template v-for="item in items" :key="item.doctype + item.name">
      <Icon name="chevron-right" :size="14" />
      <RouterLink :to="link(item)" class="max-w-[220px] truncate hover:underline" :title="item.title">{{ item.title }}</RouterLink>
    </template>
  </nav>
</template>
