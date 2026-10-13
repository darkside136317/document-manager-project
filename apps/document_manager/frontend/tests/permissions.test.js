import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("vue-router", () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ replace }) }));
vi.mock("../src/lib/api.js", () => ({
  api: { permissions: { list: vi.fn(), get: vi.fn(), save: vi.fn(), create: vi.fn(), remove: vi.fn(), reset: vi.fn() } },
  call: vi.fn(),
}));
vi.mock("../src/lib/toast.js", () => ({ toast: vi.fn(), toastError: vi.fn() }));

import RolesPage from "../src/pages/RolesPage.vue";
import { api } from "../src/lib/api.js";
import { changedMatrix, checkedCapabilities, describeChanges, editableMatrix, sortRoles, toggleCell } from "../src/lib/admin.js";

const COLUMNS = { read: "Xem", create: "Thêm", write: "Sửa", delete: "Xóa", submit: "Gửi, duyệt", cancel: "Hủy", print: "In", export: "Xuất",
  own_only: "Chỉ bản ghi của mình", sensitive: "Sửa trường nhạy cảm" };
const blank = { read: false, create: false, write: false, delete: false, submit: false, cancel: false, print: false, export: false, own_only: false, sensitive: false };

function group(overrides = {}) {
  return {
    role: "Cataloger", label: "Biên mục viên", group: "Tác nghiệp", description: "", is_builtin: true, is_admin: false, locked: false,
    modified: "2026-10-13 10:00:00", columns: COLUMNS, member_count: 1, members: [{ name: "a@x", full_name: "An", enabled: 1 }],
    matrix: [{ section: "Biên mục", rows: [
      { doctype: "Fonds", label: "Phông", columns: ["read", "create", "write", "delete", "print", "export", "own_only"], cell: { ...blank, read: true, write: true } },
      { doctype: "Archival File", label: "Hồ sơ", columns: ["read", "create", "write", "delete", "print", "export", "own_only"], cell: { ...blank } },
    ] }],
    capabilities: [{ module: "Biên mục", items: [{ code: "inventory.manage", label: "Kiểm kê", checked: true }, { code: "archive.edit_closed", label: "Sửa hồ sơ đã đóng", checked: false }] }],
    ...overrides,
  };
}

beforeEach(() => vi.clearAllMocks());

describe("matrix helpers", () => {
  it("any right brings reading, unticking reading takes every right away", () => {
    expect(toggleCell({ ...blank }, "delete", true)).toMatchObject({ read: true, delete: true });
    expect(Object.values(toggleCell({ ...blank, read: true, write: true, sensitive: true }, "read", false)).some(Boolean)).toBe(false);
    expect(toggleCell({ ...blank }, "cancel", true)).toMatchObject({ submit: true, cancel: true });
    expect(toggleCell({ ...blank, read: true, submit: true, cancel: true }, "submit", false)).toMatchObject({ submit: false, cancel: false });
  });

  it("sends only the rows that changed and says what changed in words", () => {
    const g = group();
    const edited = editableMatrix(g);
    expect(changedMatrix(editableMatrix(g), edited)).toEqual({});
    edited["Archival File"] = toggleCell(edited["Archival File"], "write", true);
    edited.Fonds = toggleCell(edited.Fonds, "write", false);
    expect(Object.keys(changedMatrix(editableMatrix(g), edited))).toEqual(["Fonds", "Archival File"]);
    const lines = describeChanges(g, edited, ["archive.edit_closed"], COLUMNS);
    expect(lines).toContain("Phông: bỏ Sửa");
    expect(lines).toContain("Hồ sơ: thêm Xem, Sửa");
    expect(lines).toContain("Thêm chức năng: Sửa hồ sơ đã đóng");
    expect(lines).toContain("Bỏ chức năng: Kiểm kê");
    expect(checkedCapabilities(g)).toEqual(["inventory.manage"]);
  });

  it("built-in groups come first, groups made later after them", () => {
    expect(sortRoles(["Zeta tự tạo", "Cataloger", "Document Admin", "Alpha tự tạo"])).toEqual(["Document Admin", "Cataloger", "Alpha tự tạo", "Zeta tự tạo"]);
  });
});

describe("RolesPage", () => {
  const stubs = { stubs: { Teleport: true, RouterLink: { template: "<a><slot /></a>" } } };

  it("opens the first group, saves only what changed and shows the change before saving", async () => {
    api.permissions.list.mockResolvedValue([{ role: "Cataloger", label: "Biên mục viên", members: 1, is_builtin: true, is_admin: false }]);
    api.permissions.get.mockResolvedValue(group());
    api.permissions.save.mockResolvedValue(group());
    const wrapper = mount(RolesPage, { global: stubs });
    await flushPromises();
    expect(api.permissions.get).toHaveBeenCalledWith("Cataloger");
    const save = wrapper.findAll("button").find((b) => b.text().includes("Lưu thay đổi"));
    expect(save.attributes("disabled")).toBeDefined();
    await wrapper.find('input[aria-label="Hồ sơ: Xóa"]').setValue(true);
    expect(save.attributes("disabled")).toBeUndefined();
    await save.trigger("click");
    expect(wrapper.text()).toContain("Hồ sơ: thêm Xem, Xóa");
    await wrapper.findAll("button").find((b) => b.text() === "Lưu").trigger("click");
    await flushPromises();
    const [role, values] = api.permissions.save.mock.calls[0];
    expect(role).toBe("Cataloger");
    expect(Object.keys(values.matrix)).toEqual(["Archival File"]);
    expect(values.matrix["Archival File"]).toMatchObject({ read: true, delete: true });
    expect(values.modified).toBe("2026-10-13 10:00:00");
  });

  it("the administrators' group is read only", async () => {
    api.permissions.list.mockResolvedValue([{ role: "Document Admin", label: "Quản trị viên", members: 2, is_builtin: true, is_admin: true }]);
    api.permissions.get.mockResolvedValue(group({ role: "Document Admin", label: "Quản trị viên", is_admin: true, locked: true }));
    const wrapper = mount(RolesPage, { global: stubs });
    await flushPromises();
    expect(wrapper.text()).toContain("Quản trị viên luôn có mọi quyền");
    expect(wrapper.findAll("button").some((b) => b.text().includes("Lưu thay đổi"))).toBe(false);
    expect(wrapper.find('input[aria-label="Phông: Sửa"]').attributes("disabled")).toBeDefined();
  });
});
