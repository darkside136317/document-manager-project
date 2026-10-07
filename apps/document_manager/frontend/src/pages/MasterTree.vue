<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import EmptyState from "../components/EmptyState.vue";
import Icon from "../components/Icon.vue";
import LinkSelect from "../components/LinkSelect.vue";
import PageHeader from "../components/PageHeader.vue";
import RecordDrawer from "../components/RecordDrawer.vue";
import TreeNode from "../components/TreeNode.vue";
import { api } from "../lib/api.js";
import { fieldByName } from "../lib/doctype.js";
import { useTree } from "../lib/useTree.js";

// Tree of one nested-set DocType (warehouse > shelf > box, classification scheme, dictionary values).
// When the DocType belongs to a list that the user picks first (a dictionary type), `master.tree_filter`
// names the field that selects it.
const props = defineProps({
  meta: { type: Object, required: true },
  master: { type: Object, required: true },
});

const filterField = computed(() => props.master.tree_filter || "");
const filterDoctype = computed(() => (filterField.value ? fieldByName(props.meta, filterField.value)?.options : ""));
const filterValue = ref("");
const hierarchical = ref(true); // a flat dictionary offers no "add child"
const filters = computed(() => (filterField.value && filterValue.value ? { [filterField.value]: filterValue.value } : null));
const ready = computed(() => !filterField.value || Boolean(filterValue.value));

const tree = useTree(props.meta.doctype, () => filters.value);
const drawer = reactive({ open: false, name: null, defaults: {} });

async function pickFirstFilterValue() {
  if (!filterField.value) return;
  try {
    const [first] = await api.linkSearch(filterDoctype.value, "");
    if (first) filterValue.value = first.value;
  } catch {
    /* the user can still pick one */
  }
}

onMounted(async () => {
  if (!filterField.value) return tree.load();
  await pickFirstFilterValue();
});

watch(filterValue, async (value) => {
  tree.reset();
  if (!value) return;
  try {
    const type = await api.get(filterDoctype.value, value);
    hierarchical.value = "is_hierarchical" in type ? Boolean(type.is_hierarchical) : true;
  } catch {
    hierarchical.value = true;
  }
  tree.load();
});

const roots = computed(() => tree.children[tree.ROOT] || []);
const canCreate = computed(() => props.meta.permissions.create && ready.value);
const canNest = computed(() => canCreate.value && hierarchical.value);

function addRoot() {
  Object.assign(drawer, { open: true, name: null, defaults: { ...(filters.value || {}) } });
}
function addChild(node) {
  Object.assign(drawer, {
    open: true, name: null, defaults: { ...(filters.value || {}), [props.meta.parent_field]: node.name },
  });
}
function edit(node) {
  Object.assign(drawer, { open: true, name: node.name, defaults: {} });
}
async function afterChange() {
  drawer.open = false;
  await tree.refresh();
}

// The parent of a record can neither be the record itself nor belong to another list.
function linkFilters(field, record) {
  if (field.fieldname !== props.meta.parent_field) return null;
  const out = {};
  if (record.name) out.name = ["!=", record.name];
  if (filterField.value && record[filterField.value]) out[filterField.value] = record[filterField.value];
  return Object.keys(out).length ? out : null;
}
</script>

<template>
  <PageHeader :title="meta.label">
    <div v-if="filterField" class="w-72">
      <LinkSelect v-model="filterValue" :doctype="filterDoctype" :clearable="false" :placeholder="`Chọn ${fieldByName(meta, filterField)?.label?.toLowerCase() || ''}...`" />
    </div>
    <button v-if="canCreate" class="btn btn-primary" type="button" @click="addRoot"><Icon name="plus" :size="16" /> {{ filterField ? "Thêm giá trị" : "Thêm mục gốc" }}</button>
  </PageHeader>

  <p v-if="tree.state.error" class="mb-4 whitespace-pre-line rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ tree.state.error }}</p>

  <section class="card p-2">
    <EmptyState v-if="!ready" icon="book-a" title="Chọn một loại để xem các giá trị" text="Tạo loại mới ở mục “Loại từ điển” nếu chưa có." />
    <div v-else-if="tree.loading[tree.ROOT] && !roots.length" class="flex items-center gap-2 px-4 py-8 text-ink-muted"><Icon name="loader" spin /> Đang tải...</div>
    <EmptyState v-else-if="!roots.length" icon="inbox" :title="`Chưa có ${meta.label.toLowerCase()}`" />
    <ul v-else class="m-0 list-none p-0" role="tree">
      <TreeNode v-for="node in roots" :key="node.name" :node="node" :tree="tree" :meta="meta" :can-create="canNest" @edit="edit" @add-child="addChild" />
    </ul>
  </section>

  <RecordDrawer :open="drawer.open" :meta="meta" :name="drawer.name" :defaults="drawer.defaults" :link-filters="linkFilters" @close="drawer.open = false" @saved="afterChange" @deleted="afterChange" />
</template>
