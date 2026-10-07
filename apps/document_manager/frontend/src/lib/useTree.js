// Lazy-loaded tree of a nested-set DocType: children are fetched when a node is opened.
import { reactive } from "vue";
import { api } from "./api.js";

const ROOT = "";

export function useTree(doctype, getFilters = () => null) {
  const children = reactive({}); // parent name ("" = roots) -> rows
  const expanded = reactive({}); // node name -> true
  const loading = reactive({});
  const state = reactive({ error: "" });

  async function load(parent = ROOT) {
    loading[parent] = true;
    try {
      children[parent] = await api.treeChildren(doctype, parent || null, getFilters());
      state.error = "";
    } catch (e) {
      state.error = e.message;
      children[parent] = children[parent] || [];
    } finally {
      loading[parent] = false;
    }
  }

  async function toggle(node) {
    if (expanded[node.name]) {
      delete expanded[node.name];
      return;
    }
    expanded[node.name] = true;
    if (!children[node.name]) await load(node.name);
  }

  /** Reload the roots and every opened branch, keeping the user's place. */
  async function refresh() {
    const opened = Object.keys(expanded);
    await Promise.all([load(ROOT), ...opened.map((name) => load(name))]);
  }

  function reset() {
    for (const key of Object.keys(children)) delete children[key];
    for (const key of Object.keys(expanded)) delete expanded[key];
  }

  return { children, expanded, loading, state, load, toggle, refresh, reset, ROOT };
}
