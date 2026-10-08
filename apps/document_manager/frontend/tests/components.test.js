import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive } from "vue";

vi.mock("../src/lib/api.js", () => ({
  api: {
    linkSearch: vi.fn(),
    treeChildren: vi.fn(),
  },
  call: vi.fn(),
}));

import { api } from "../src/lib/api.js";
import ConfirmDialog from "../src/components/ConfirmDialog.vue";
import FieldInput from "../src/components/FieldInput.vue";
import FormRenderer from "../src/components/FormRenderer.vue";
import LinkSelect from "../src/components/LinkSelect.vue";
import PaginationBar from "../src/components/PaginationBar.vue";
import TreeNode from "../src/components/TreeNode.vue";
import { useTree } from "../src/lib/useTree.js";

const field = (extra) => ({ fieldname: "f", label: "Nhãn", fieldtype: "Data", options: "", reqd: false, read_only: false, description: "", ...extra });

beforeEach(() => vi.clearAllMocks());

describe("FieldInput", () => {
  it("emits the typed text for a Data field", async () => {
    const wrapper = mount(FieldInput, { props: { field: field({}), modelValue: "" } });
    await wrapper.find("input").setValue("xin chào");
    expect(wrapper.emitted("update:modelValue")[0]).toEqual(["xin chào"]);
  });

  it("emits numbers (or null) for Int fields", async () => {
    const wrapper = mount(FieldInput, { props: { field: field({ fieldtype: "Int" }), modelValue: null } });
    await wrapper.find("input").setValue("42");
    await wrapper.find("input").setValue("");
    expect(wrapper.emitted("update:modelValue")).toEqual([[42], [null]]);
  });

  it("emits 1 / 0 for a checkbox", async () => {
    const wrapper = mount(FieldInput, { props: { field: field({ fieldtype: "Check" }), modelValue: 0 } });
    await wrapper.find("input[type=checkbox]").setValue(true);
    await wrapper.find("input[type=checkbox]").setValue(false);
    expect(wrapper.emitted("update:modelValue")).toEqual([[1], [0]]);
  });

  it("offers the options of a Select, with a prompt for the blank one", () => {
    const wrapper = mount(FieldInput, { props: { field: field({ fieldtype: "Select", options: "\nTrung tâm\nThư viện" }), modelValue: "" } });
    expect(wrapper.findAll("option").map((o) => o.text())).toEqual(["— Chọn —", "Trung tâm", "Thư viện"]);
  });

  it("marks required fields and shows the error instead of the description", () => {
    const wrapper = mount(FieldInput, { props: { field: field({ reqd: true, description: "Gợi ý" }), modelValue: "", error: "Thiếu" } });
    expect(wrapper.find("label").text()).toContain("*");
    expect(wrapper.text()).toContain("Thiếu");
    expect(wrapper.text()).not.toContain("Gợi ý");
    expect(wrapper.find("input").classes()).toContain("is-invalid");
  });

  it("does not let a read-only field be edited", () => {
    const wrapper = mount(FieldInput, { props: { field: field({}), modelValue: "x", readOnly: true } });
    expect(wrapper.find("input").attributes("disabled")).toBeDefined();
  });
});

describe("FormRenderer", () => {
  const meta = {
    name_field: "code",
    fields: [field({ fieldname: "code", label: "Mã" }), field({ fieldname: "title", label: "Tên" }), field({ fieldname: "gone", label: "Ẩn" })],
    layout: [{ title: "Chung", columns: [["code"], ["title"]] }, { title: null, columns: [["gone"]] }],
  };

  it("draws every field of every section, in order, with the section titles", () => {
    const wrapper = mount(FormRenderer, { props: { meta, record: reactive({ code: "A", title: "B", gone: "" }) } });
    expect(wrapper.findAll("label").map((l) => l.text())).toEqual(["Mã", "Tên", "Ẩn"]);
    expect(wrapper.find("h3").text()).toBe("Chung");
  });

  it("edits the record in place", async () => {
    const record = reactive({ code: "A", title: "B", gone: "" });
    const wrapper = mount(FormRenderer, { props: { meta, record } });
    await wrapper.find("#f-title").setValue("Mới");
    expect(record.title).toBe("Mới");
  });

  it("locks the field a record's name comes from once the record exists", () => {
    const wrapper = mount(FormRenderer, { props: { meta, record: reactive({ code: "A", title: "B", gone: "" }), editing: true } });
    expect(wrapper.find("#f-code").attributes("disabled")).toBeDefined();
    expect(wrapper.find("#f-title").attributes("disabled")).toBeUndefined();
    const fresh = mount(FormRenderer, { props: { meta, record: reactive({ code: "", title: "", gone: "" }), editing: false } });
    expect(fresh.find("#f-code").attributes("disabled")).toBeUndefined();
  });

  it("is read-only as a whole when the user cannot write", () => {
    const wrapper = mount(FormRenderer, { props: { meta, record: reactive({ code: "A", title: "B", gone: "" }), readOnly: true } });
    expect(wrapper.findAll("input").every((i) => i.attributes("disabled") !== undefined)).toBe(true);
  });
});

describe("LinkSelect", () => {
  it("searches while typing, lists the options and emits the chosen value", async () => {
    api.linkSearch.mockImplementation(async (_doctype, text) =>
      text === "" ? [{ value: "A1", label: "Agency 1", description: "" }] : [{ value: "A2", label: "Agency 2", description: "A2" }]);
    const wrapper = mount(LinkSelect, { props: { modelValue: "", doctype: "Archival Agency" } });
    await wrapper.find("input").trigger("focus");
    await flushPromises();
    expect(wrapper.findAll("[role=option]").map((o) => o.text())).toEqual(["Agency 1"]);

    vi.useFakeTimers();
    await wrapper.find("input").setValue("ag");
    vi.advanceTimersByTime(300);
    vi.useRealTimers();
    await flushPromises();
    expect(api.linkSearch).toHaveBeenLastCalledWith("Archival Agency", "ag", null);
    await wrapper.find("[role=option]").trigger("mousedown");
    expect(wrapper.emitted("update:modelValue")[0]).toEqual(["A2"]);
  });

  it("shows the label of the current value, not its raw name", async () => {
    api.linkSearch.mockResolvedValue([{ value: "FONDS-1", label: "Phông Quốc hội", description: "FONDS-1" }]);
    const wrapper = mount(LinkSelect, { props: { modelValue: "FONDS-1", doctype: "Fonds" } });
    await flushPromises();
    expect(wrapper.find("input").element.value).toBe("Phông Quốc hội");
  });

  it("passes the filters through and can be cleared", async () => {
    api.linkSearch.mockResolvedValue([]);
    const wrapper = mount(LinkSelect, { props: { modelValue: "X", doctype: "Quick Entry Dictionary", filters: { dictionary_type: "T" } } });
    await flushPromises();
    expect(api.linkSearch).toHaveBeenCalledWith("Quick Entry Dictionary", "X", { dictionary_type: "T" });
    await wrapper.find("button[aria-label='Bỏ chọn']").trigger("mousedown");
    expect(wrapper.emitted("update:modelValue")[0]).toEqual([""]);
  });

  it("does not open when disabled", async () => {
    const wrapper = mount(LinkSelect, { props: { modelValue: "", doctype: "Fonds", disabled: true } });
    await wrapper.find("input").trigger("focus");
    expect(api.linkSearch).not.toHaveBeenCalled();
  });
});

describe("tree", () => {
  const rows = {
    "": [{ name: "ROOT", warehouse_name: "Kho 1", child_count: 1 }, { name: "LEAF", warehouse_name: "Kho 2", child_count: 0 }],
    ROOT: [{ name: "SHELF", warehouse_name: "Giá 1", child_count: 0 }],
  };
  const meta = { title_field: "warehouse_name", list_fields: ["warehouse_name"] };

  it("loads children only when a node is opened, and keeps the place on refresh", async () => {
    api.treeChildren.mockImplementation(async (_doctype, parent) => rows[parent || ""] || []);
    const tree = useTree("Storage Warehouse");
    await tree.load();
    expect(tree.children[""].map((r) => r.name)).toEqual(["ROOT", "LEAF"]);
    expect(api.treeChildren).toHaveBeenCalledTimes(1);

    await tree.toggle(tree.children[""][0]);
    expect(tree.expanded.ROOT).toBe(true);
    expect(tree.children.ROOT[0].name).toBe("SHELF");
    await tree.toggle(tree.children[""][0]);
    expect(tree.expanded.ROOT).toBeUndefined();

    await tree.toggle(tree.children[""][0]);
    api.treeChildren.mockClear();
    await tree.refresh();
    expect(api.treeChildren.mock.calls.map((c) => c[1])).toEqual([null, "ROOT"]);
  });

  it("passes the active filters on every request and forgets everything on reset", async () => {
    api.treeChildren.mockResolvedValue([]);
    let filters = { dictionary_type: "A" };
    const tree = useTree("Quick Entry Dictionary", () => filters);
    await tree.load();
    filters = { dictionary_type: "B" };
    tree.reset();
    expect(Object.keys(tree.children)).toEqual([]);
    await tree.load();
    expect(api.treeChildren).toHaveBeenLastCalledWith("Quick Entry Dictionary", null, { dictionary_type: "B" });
  });

  it("shows a node's title and child count, and offers to add a child only when allowed", async () => {
    api.treeChildren.mockResolvedValue([]);
    const tree = useTree("Storage Warehouse");
    const node = { name: "ROOT", warehouse_name: "Kho 1", child_count: 3 };
    const wrapper = mount(TreeNode, { props: { node, tree, meta, canCreate: true } });
    expect(wrapper.text()).toContain("Kho 1");
    expect(wrapper.find(".badge").text()).toBe("3");
    await wrapper.find("[title='Thêm mục con']").trigger("click");
    expect(wrapper.emitted("add-child")[0][0]).toEqual(node);
    await wrapper.find("button.min-w-0").trigger("click");
    expect(wrapper.emitted("edit")[0][0]).toEqual(node);
    const readOnly = mount(TreeNode, { props: { node, tree, meta, canCreate: false } });
    expect(readOnly.find("[title='Thêm mục con']").exists()).toBe(false);
  });
});

describe("dialogs and paging", () => {
  it("ConfirmDialog confirms, cancels and shows the server's refusal", async () => {
    const wrapper = mount(ConfirmDialog, {
      props: { open: true, title: "Xóa", message: "Chắc chứ?", error: "Đang được dùng", danger: true, confirmText: "Xóa" },
      global: { stubs: { teleport: true } },
    });
    expect(wrapper.text()).toContain("Đang được dùng");
    const [cancel, confirm] = wrapper.findAll("button");
    await confirm.trigger("click");
    await cancel.trigger("click");
    expect(wrapper.emitted("confirm")).toHaveLength(1);
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("PaginationBar reports the range and disables the ends", async () => {
    const wrapper = mount(PaginationBar, { props: { page: 1, pageSize: 20, total: 45 } });
    expect(wrapper.text()).toContain("1–20 / 45");
    expect(wrapper.text()).toContain("Trang 1 / 3");
    const [prev, next] = wrapper.findAll("button");
    expect(prev.attributes("disabled")).toBeDefined();
    await next.trigger("click");
    expect(wrapper.emitted("change")[0]).toEqual([2]);
    const last = mount(PaginationBar, { props: { page: 3, pageSize: 20, total: 45 } });
    expect(last.text()).toContain("41–45 / 45");
    expect(last.findAll("button")[1].attributes("disabled")).toBeDefined();
    expect(mount(PaginationBar, { props: { total: 0 } }).text()).toContain("0–0 / 0");
  });

  it("PaginationBar says '+' when the total stopped at its ceiling", () => {
    const capped = mount(PaginationBar, { props: { page: 1, pageSize: 20, total: 10000, capped: true } });
    expect(capped.text()).toContain("1–20 / 10.000+");
    expect(mount(PaginationBar, { props: { page: 1, pageSize: 20, total: 10000 } }).text()).not.toContain("+");
  });
});
