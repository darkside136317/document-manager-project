<script setup>
import { computed } from "vue";
import Icon from "./Icon.vue";

// One row of the tree and, when opened, its children (recursive).
const props = defineProps({
  node: { type: Object, required: true },
  tree: { type: Object, required: true },
  meta: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  canCreate: { type: Boolean, default: false },
});
const emit = defineEmits(["edit", "add-child"]);

const open = computed(() => Boolean(props.tree.expanded[props.node.name]));
const hasChildren = computed(() => Boolean(props.node.child_count));
const kids = computed(() => props.tree.children[props.node.name] || []);
const title = computed(() => props.node[props.meta.title_field] || props.node.name);
const code = computed(() => {
  const field = props.meta.list_fields.find((f) => f.endsWith("_code"));
  return field ? props.node[field] : "";
});
const inactive = computed(() => props.node.is_active === 0);
</script>

<template>
  <li role="treeitem" :aria-expanded="hasChildren ? open : undefined">
    <div class="group flex items-center gap-1 rounded-md py-1 pr-2 hover:bg-surface-muted" :style="{ paddingLeft: `${depth * 22 + 6}px` }">
      <button
        v-if="hasChildren"
        class="grid h-6 w-6 place-items-center rounded text-ink-muted hover:bg-surface"
        type="button"
        :aria-label="open ? 'Thu gọn' : 'Mở rộng'"
        @click="tree.toggle(node)"
      >
        <Icon :name="tree.loading[node.name] ? 'loader' : open ? 'chevron-down' : 'chevron-right'" :size="15" :spin="Boolean(tree.loading[node.name])" />
      </button>
      <span v-else class="inline-block h-6 w-6"></span>
      <Icon :name="hasChildren ? (open ? 'folder-open' : 'folder') : 'file-text'" :size="16" class="text-ink-muted" />
      <button class="min-w-0 flex-1 truncate rounded px-1 text-left text-sm font-medium hover:underline" type="button" :class="{ 'text-ink-subtle line-through': inactive }" @click="emit('edit', node)">
        {{ title }}
      </button>
      <span v-if="code" class="hidden text-xs text-ink-muted sm:inline">{{ code }}</span>
      <span v-if="hasChildren" class="badge badge-muted">{{ node.child_count }}</span>
      <button v-if="canCreate" class="btn btn-ghost btn-icon !min-h-0 !p-1 opacity-0 focus:opacity-100 group-hover:opacity-100" type="button" title="Thêm mục con" aria-label="Thêm mục con" @click="emit('add-child', node)">
        <Icon name="plus" :size="15" />
      </button>
    </div>
    <ul v-if="open" role="group" class="m-0 list-none p-0">
      <TreeNode v-for="child in kids" :key="child.name" :node="child" :tree="tree" :meta="meta" :depth="depth + 1" :can-create="canCreate" @edit="emit('edit', $event)" @add-child="emit('add-child', $event)" />
    </ul>
  </li>
</template>
