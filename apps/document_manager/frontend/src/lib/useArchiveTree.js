// Lazy tree of the cataloguing hierarchy: fonds > record groups > catalogs. Nodes are keyed by
// "Doctype:name" because the three levels are different DocTypes.
import { reactive } from "vue";
import { api } from "./api.js";

export const nodeKey = (node) => (node ? `${node.doctype}:${node.name}` : "");

export function useArchiveTree() {
  const children = reactive({}); // parent key ("" = roots) -> nodes
  const expanded = reactive({}); // node key -> true
  const loading = reactive({});
  const state = reactive({ error: "" });

  async function load(parent = null) {
    const key = nodeKey(parent);
    loading[key] = true;
    try {
      children[key] = await api.archive.tree(parent?.doctype ?? null, parent?.name ?? null);
      state.error = "";
    } catch (e) {
      state.error = e.message;
      children[key] = children[key] || [];
    } finally {
      loading[key] = false;
    }
  }

  async function toggle(node) {
    const key = nodeKey(node);
    if (expanded[key]) {
      delete expanded[key];
      return;
    }
    expanded[key] = true;
    if (!children[key]) await load(node);
  }

  /** Open the branches down to `chain` ([fonds, group, catalog] as {doctype, name}) so the last one is visible. */
  async function reveal(chain) {
    if (!children[""]) await load(null);
    for (const node of chain) {
      const key = nodeKey(node);
      if (!children[key] && node.doctype !== "Catalog") await load(node);
      if (node.doctype !== "Catalog") expanded[key] = true;
    }
  }

  async function refresh() {
    const parents = Object.keys(expanded).map((key) => {
      const [doctype, ...rest] = key.split(":");
      return { doctype, name: rest.join(":") };
    });
    await Promise.all([load(null), ...parents.map((node) => load(node))]);
  }

  return { children, expanded, loading, state, load, toggle, reveal, refresh };
}
