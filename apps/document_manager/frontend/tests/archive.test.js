import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("../src/lib/api.js", () => ({
  api: {
    linkSearch: vi.fn(),
    archive: { tree: vi.fn(), addDocument: vi.fn(), attachFile: vi.fn() },
    search: { files: vi.fn(), documents: vi.fn() },
  },
  call: vi.fn(),
}));
vi.mock("../src/lib/boot.js", () => ({
  boot: {
    nav: [{ group: "Biên mục", items: [{ label: "Tìm kiếm", route: "/dashboard/tim-kiem", icon: "search" }, { label: "Tổng quan", route: "/dashboard", icon: "layout-dashboard" }] }],
    masters: [], archive: [{ doctype: "Archival File" }], legacy: [], user: { roles: [] }, org: "T",
  },
  csrfToken: () => "token",
  initials: (n) => n,
  masterBySlug: () => null,
}));

import { api } from "../src/lib/api.js";
import Breadcrumbs from "../src/components/Breadcrumbs.vue";
import CommandPalette from "../src/components/CommandPalette.vue";
import DataTable from "../src/components/DataTable.vue";
import DocumentPreview from "../src/components/DocumentPreview.vue";
import FileUploader from "../src/components/FileUploader.vue";
import { nodeKey, useArchiveTree } from "../src/lib/useArchiveTree.js";

const routerFor = () => createRouter({ history: createMemoryHistory(), routes: [{ path: "/:p(.*)*", component: { template: "<div/>" } }] });
beforeEach(() => vi.clearAllMocks());

describe("archive tree", () => {
  const nodes = {
    "": [{ doctype: "Fonds", name: "F1", title: "Phông 1", child_count: 1 }],
    "Fonds:F1": [{ doctype: "Record Group", name: "RG1", title: "Khối 1", child_count: 1 }],
    "Record Group:RG1": [{ doctype: "Catalog", name: "C1", title: "Mục lục 1", child_count: 0 }],
  };
  const respond = async (doctype, name) => nodes[doctype ? `${doctype}:${name}` : ""] || [];

  it("keys nodes by doctype and name", () => {
    expect(nodeKey({ doctype: "Catalog", name: "C:1" })).toBe("Catalog:C:1");
    expect(nodeKey(null)).toBe("");
  });

  it("opens the branches down to a catalog so that it is visible", async () => {
    api.archive.tree.mockImplementation(respond);
    const tree = useArchiveTree();
    await tree.reveal([{ doctype: "Fonds", name: "F1" }, { doctype: "Record Group", name: "RG1" }, { doctype: "Catalog", name: "C1" }]);
    expect(tree.children[""][0].name).toBe("F1");
    expect(tree.children["Fonds:F1"][0].name).toBe("RG1");
    expect(tree.children["Record Group:RG1"][0].name).toBe("C1");
    expect(tree.expanded["Fonds:F1"] && tree.expanded["Record Group:RG1"]).toBe(true);
    expect(tree.expanded["Catalog:C1"]).toBeUndefined(); // catalogs are leaves
    expect(api.archive.tree).not.toHaveBeenCalledWith("Catalog", "C1");
  });

  it("reloads the roots and the opened branches on refresh, and loads a branch only once opened", async () => {
    api.archive.tree.mockImplementation(respond);
    const tree = useArchiveTree();
    await tree.load(null);
    expect(api.archive.tree).toHaveBeenCalledTimes(1);
    await tree.toggle(tree.children[""][0]);
    expect(tree.expanded["Fonds:F1"]).toBe(true);
    api.archive.tree.mockClear();
    await tree.refresh();
    expect(api.archive.tree.mock.calls).toEqual([[null, null], ["Fonds", "F1"]]);
    await tree.toggle(tree.children[""][0]);
    expect(tree.expanded["Fonds:F1"]).toBeUndefined();
  });

  it("keeps an empty list and the message when the server refuses", async () => {
    api.archive.tree.mockRejectedValue(new Error("Không có quyền"));
    const tree = useArchiveTree();
    await tree.load(null);
    expect(tree.state.error).toBe("Không có quyền");
    expect(tree.children[""]).toEqual([]);
  });
});

describe("Breadcrumbs", () => {
  it("links the crumbs to the cataloguing browser and to the file", async () => {
    const router = routerFor();
    const wrapper = mount(Breadcrumbs, {
      props: { items: [{ doctype: "Fonds", name: "F1", title: "Phông 1" }, { doctype: "Archival File", name: "AF-1", title: "Hồ sơ 1" }] },
      global: { plugins: [router] },
    });
    const hrefs = wrapper.findAll("a").map((a) => a.attributes("href"));
    expect(hrefs).toEqual(["/bien-muc", "/bien-muc?node=Fonds:F1", "/ho-so/AF-1"]);
    expect(wrapper.text()).toContain("Phông 1");
  });
});

describe("DataTable", () => {
  const meta = {
    columns: [
      { fieldname: "document_title", label: "Tiêu đề", fieldtype: "Data" },
      { fieldname: "file_size_kb", label: "Dung lượng", fieldtype: "Float" },
      { fieldname: "search_index_status", label: "Chỉ mục", fieldtype: "Select" },
    ],
  };
  it("shows columns the form hides, sizes in human units and statuses as badges", async () => {
    const wrapper = mount(DataTable, { props: { meta, rows: [{ name: "D1", document_title: "Công văn", file_size_kb: 2048, search_index_status: "Đã index" }] } });
    expect(wrapper.findAll("th").map((t) => t.text()).slice(0, 3)).toEqual(["Tiêu đề", "Dung lượng", "Chỉ mục"]);
    expect(wrapper.text()).toContain("2.0 MB");
    expect(wrapper.find(".badge-success").text()).toBe("Đã index");
    await wrapper.find("tbody tr").trigger("click");
    expect(wrapper.emitted("open")[0][0].name).toBe("D1");
    await wrapper.find("thead button").trigger("click");
    expect(wrapper.emitted("sort")[0]).toEqual(["document_title"]);
  });
});

describe("DocumentPreview", () => {
  const base = { title: "T", file_type: "PDF" };
  it("frames a PDF, shows an image, prints extracted text and explains the rest", () => {
    const pdf = mount(DocumentPreview, { props: { attached: true, preview: { ...base, kind: "inline", preview_url: "/p.pdf" } } });
    expect(pdf.find("iframe").attributes("src")).toBe("/p.pdf");
    const image = mount(DocumentPreview, { props: { attached: true, preview: { ...base, file_type: "PNG", kind: "inline", preview_url: "/p.png" } } });
    expect(image.find("img").attributes("src")).toBe("/p.png");
    const text = mount(DocumentPreview, { props: { attached: true, preview: { ...base, kind: "text", content: "nội dung <b>x</b>", notice: "Bản trích xuất" } } });
    expect(text.find("pre").text()).toBe("nội dung <b>x</b>"); // shown as text, not as markup
    const other = mount(DocumentPreview, { props: { attached: true, preview: { ...base, kind: "unsupported", notice: "Tải về để xem" } } });
    expect(other.text()).toContain("Tải về để xem");
  });
  it("says so when there is no file, a failure or it is loading", () => {
    expect(mount(DocumentPreview, { props: { attached: false } }).text()).toContain("chưa có tệp");
    expect(mount(DocumentPreview, { props: { attached: true, error: "Lỗi đọc" } }).text()).toContain("Lỗi đọc");
    expect(mount(DocumentPreview, { props: { attached: true, loading: true } }).text()).toContain("Đang tải");
  });
});

describe("FileUploader", () => {
  const rules = { extensions: ["pdf"], max_mb: 1 };
  const pick = async (wrapper, files) => {
    const input = wrapper.find("input[type=file]");
    Object.defineProperty(input.element, "files", { value: files, configurable: true });
    await input.trigger("change");
  };

  it("lists picked files, marks an invalid one with its reason and uploads only the valid ones", async () => {
    const wrapper = mount(FileUploader, { props: { rules, archivalFile: "AF-1" }, global: { plugins: [routerFor()] } });
    await pick(wrapper, [{ name: "a.pdf", size: 10 }, { name: "b.exe", size: 10 }]);
    expect(wrapper.findAll("li")).toHaveLength(2);
    expect(wrapper.text()).toContain("không được hỗ trợ");
    const button = wrapper.find("button.btn-primary");
    expect(button.text()).toContain("Tải lên 1 tệp");
    expect(button.attributes("disabled")).toBeUndefined();
  });

  it("in replace mode takes a single file", async () => {
    const wrapper = mount(FileUploader, { props: { rules, mode: "replace", document: "DOC-1" }, global: { plugins: [routerFor()] } });
    await pick(wrapper, [{ name: "a.pdf", size: 10 }, { name: "c.pdf", size: 10 }]);
    expect(wrapper.findAll("li")).toHaveLength(1);
    expect(wrapper.find("input[type=file]").attributes("multiple")).toBeUndefined();
    expect(wrapper.find("button.btn-primary").text()).toContain("Thay tệp");
  });

  it("cannot start with nothing to upload", () => {
    const wrapper = mount(FileUploader, { props: { rules, archivalFile: "AF-1" }, global: { plugins: [routerFor()] } });
    expect(wrapper.find("button.btn-primary").attributes("disabled")).toBeDefined();
  });
});

describe("CommandPalette", () => {
  const mountPalette = async () => {
    const router = routerFor();
    const push = vi.spyOn(router, "push");
    const wrapper = mount(CommandPalette, { props: { open: true }, global: { plugins: [router], stubs: { teleport: true } } });
    await flushPromises();
    return { wrapper, push };
  };

  it("lists the screens first and filters them while typing", async () => {
    const { wrapper } = await mountPalette();
    expect(wrapper.findAll("[role=option]").map((o) => o.text())).toEqual(["Tìm kiếm", "Tổng quan"]);
    await wrapper.find("input").setValue("tổng");
    await flushPromises();
    expect(wrapper.findAll("[role=option]").map((o) => o.text())).toContain("Tổng quan");
    expect(wrapper.text()).not.toContain("Tìm kiếm\n");
  });

  it("searches files and documents and opens the chosen one", async () => {
    api.search.files.mockResolvedValue({ data: [{ name: "AF-1", file_title: "Hồ sơ Quốc hội", file_number: "01" }] });
    api.search.documents.mockResolvedValue({ data: [{ id: "DOC-7", document_title: "Nghị quyết", document_number: "NQ-1" }] });
    const { wrapper, push } = await mountPalette();
    vi.useFakeTimers();
    await wrapper.find("input").setValue("quốc");
    vi.advanceTimersByTime(300);
    vi.useRealTimers();
    await flushPromises();
    const labels = wrapper.findAll("[role=option]").map((o) => o.text());
    expect(labels.some((l) => l.includes("Hồ sơ Quốc hội"))).toBe(true);
    expect(labels.some((l) => l.includes("Nghị quyết"))).toBe(true);
    expect(labels.at(-1)).toContain("Tìm nâng cao");
    await wrapper.findAll("[role=option]").find((o) => o.text().includes("Nghị quyết")).trigger("click");
    expect(push).toHaveBeenCalledWith("/van-ban/DOC-7");
    expect(wrapper.emitted("close")).toBeTruthy();
  });

  it("does not search for a single character, navigates with the keyboard and closes on Escape", async () => {
    const { wrapper, push } = await mountPalette();
    await wrapper.find("input").setValue("a");
    vi.useFakeTimers();
    vi.advanceTimersByTime(400);
    vi.useRealTimers();
    expect(api.search.files).not.toHaveBeenCalled();
    await wrapper.find("input").trigger("keydown", { key: "ArrowDown" });
    await wrapper.find("input").trigger("keydown", { key: "Enter" });
    expect(push).toHaveBeenCalled();
    await wrapper.find("input").trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("close").length).toBeGreaterThanOrEqual(2);
  });
});
