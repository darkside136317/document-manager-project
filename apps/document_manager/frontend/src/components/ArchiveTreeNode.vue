<script setup>
import { computed } from "vue";
import { nodeKey } from "../lib/useArchiveTree.js";
import { formatNumber } from "../lib/format.js";
import Icon from "./Icon.vue";

const props = defineProps({
  node: { type: Object, required: true },
  tree: { type: Object, required: true },
  selected: { type: String, default: "" },
  depth: { type: Number, default: 0 },
});
const emit = defineEmits(["select"]);

const key = computed(() => nodeKey(props.node));
const open = computed(() => Boolean(props.tree.expanded[key.value]));
const hasChildren = computed(() => props.node.child_count > 0);
const kids = computed(() => props.tree.children[key.value] || []);
const icon = computed(() => ({ Fonds: "library", "Record Group": "layers", Catalog: "book-open-text" })[props.node.doctype]);
</script>

<template>
  <li role="treeitem" :aria-expanded="hasChildren ? open : undefined" :aria-selected="selected === key">
    <div
      class="group flex items-center gap-1 rounded-md py-1 pr-2"
      :class="selected === key ? 'bg-primary-soft' : 'hover:bg-surface-muted'"
      :style="{ paddingLeft: `${depth * 18 + 4}px` }"
    >
      <button v-if="hasChildren" class="grid h-6 w-6 shrink-0 place-items-center rounded text-ink-muted hover:bg-surface" type="button" :aria-label="open ? 'Thu gọn' : 'Mở rộng'" @click="tree.toggle(node)">
        <Icon :name="tree.loading[key] ? 'loader' : open ? 'chevron-down' : 'chevron-right'" :size="15" :spin="Boolean(tree.loading[key])" />
      </button>
      <span v-else class="inline-block h-6 w-6 shrink-0"></span>
      <button class="flex min-w-0 flex-1 items-center gap-2 rounded px-1 py-0.5 text-left" type="button" :title="node.title" @click="emit('select', node)">
        <Icon :name="icon" :size="16" class="shrink-0 text-ink-muted" />
        <span class="truncate text-sm" :class="selected === key ? 'font-semibold' : 'font-medium'">{{ node.title }}</span>
      </button>
      <span v-if="node.file_count" class="badge badge-muted shrink-0" :title="`${node.file_count} hồ sơ`">{{ formatNumber(node.file_count) }}</span>
    </div>
    <ul v-if="open" role="group" class="m-0 list-none p-0">
      <ArchiveTreeNode v-for="child in kids" :key="nodeKey(child)" :node="child" :tree="tree" :selected="selected" :depth="depth + 1" @select="emit('select', $event)" />
    </ul>
  </li>
</template>
