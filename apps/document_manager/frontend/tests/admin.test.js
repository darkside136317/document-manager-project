import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/lib/api.js", () => ({
  api: {
    preservation: { job: vi.fn(), findings: vi.fn(), cancel: vi.fn(), resume: vi.fn(), remove: vi.fn(), verifyBackup: vi.fn(), startRestore: vi.fn(), setFinding: vi.fn(), fixCounters: vi.fn(), prepareDbRestore: vi.fn(), runRestore: vi.fn() },
  },
  call: vi.fn(),
}));

import PreserveJobDrawer from "../src/components/PreserveJobDrawer.vue";
import {
  blankUser, canEditUser, changedValues, cleanLogFilters, diskTone, indexTone, latestPurgeDate, logDownloadUrl, permissionText, prettyJson,
  purgeConfirmed, queueText, serviceTone, sortRoles, toggleValue, userProblem, userToForm,
} from "../src/lib/admin.js";
import { api } from "../src/lib/api.js";
import {
  ageText, ageTone, codeLabel, confirmMatches, downloadBackupUrl, formatBytes, formatMb, isCounterCode, jobResult, jobType, parseNames,
} from "../src/lib/preservation.js";

beforeEach(() => vi.clearAllMocks());

describe("preservation helpers", () => {
  it("names the findings in words, and knows which ones recomputing the counters mends", () => {
    expect(codeLabel("FILE_MISSING")).toBe("Mất tệp");
    expect(codeLabel("CHECKSUM")).toBe("Tệp đã thay đổi");
    expect(codeLabel("META_DOCUMENT_NUMBER")).toBe("Thiếu siêu dữ liệu");
    expect(codeLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
    expect(codeLabel("")).toBe("");
    expect(isCounterCode("COUNTER_FONDS")).toBe(true);
    expect(isCounterCode("ORPHAN_FILE")).toBe(false);
  });

  it("tells what a job did in a few words", () => {
    expect(jobResult("backup", { database: { file: "x.gz", size_mb: 12 }, files: { total: 10, done: 8, failed: 2 } })).toBe("CSDL 12 MB · 8/10 tệp, 2 lỗi");
    expect(jobResult("backup", { database: { file: "" }, files: { total: 0, done: 0, failed: 0 } })).toBe("—");
    expect(jobResult("integrity", { total_checked: 40, errors: 1, warnings: 3 })).toBe("40 tài liệu · 1 lỗi · 3 cảnh báo");
    expect(jobResult("restore", { restore_type: "Tệp tài liệu", restored: 3, total: 4, failed: 1 })).toBe("3/4 tài liệu, 1 lỗi");
    expect(jobResult("restore", { restore_type: "Cơ sở dữ liệu" })).toBe("Cơ sở dữ liệu");
    expect(jobType("integrity", { check_type: "Toàn bộ" })).toBe("Toàn bộ");
  });

  it("formats sizes and ages", () => {
    expect(formatMb(2048)).toBe("2.0 GB");
    expect(formatMb(0.5)).toBe("0.5 MB");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 ** 2)).toBe("5.0 MB");
    expect(ageText(null)).toBe("chưa có");
    expect(ageText(0)).toBe("hôm nay");
    expect(ageText(3)).toBe("3 ngày trước");
  });

  it("colours the age of the last backup against the schedule", () => {
    expect(ageTone(null, "Hàng ngày")).toBe("danger");
    expect(ageTone(0, "Hàng tuần")).toBe("success");
    expect(ageTone(6, "Hàng tuần")).toBe("warning");
    expect(ageTone(20, "Hàng tuần")).toBe("danger");
    expect(ageTone(3, "Hàng ngày")).toBe("danger");
  });

  it("reads document names however they were typed and asks for the site name to run a restore", () => {
    expect(parseNames("DOC-1, DOC-2\nDOC-1  DOC-3;")).toEqual(["DOC-1", "DOC-2", "DOC-3"]);
    expect(parseNames("")).toEqual([]);
    expect(confirmMatches(" docmanager.example.com ", "docmanager.example.com")).toBe(true);
    expect(confirmMatches("other", "docmanager.example.com")).toBe(false);
    expect(confirmMatches("x", "")).toBe(false);
    expect(downloadBackupUrl("BK-1", "manifest")).toContain("which=manifest");
  });
});

describe("administration helpers", () => {
  const original = { name: "an@x.vn", first_name: "An", last_name: "Nguyen", phone: "", enabled: 1, roles: ["Cataloger", "Document Admin"], groups: ["Nhóm A"], protected: false };

  it("starts a user form blank and fills it from an account", () => {
    expect(blankUser()).toEqual({ email: "", first_name: "", last_name: "", phone: "", enabled: 1, roles: [], groups: [] });
    expect(userToForm(original)).toMatchObject({ email: "an@x.vn", first_name: "An", roles: ["Cataloger", "Document Admin"] });
  });

  it("sends only what changed, whatever order roles and groups are in", () => {
    const form = userToForm(original);
    expect(changedValues(original, form)).toEqual({});
    expect(changedValues(original, { ...form, roles: ["Document Admin", "Cataloger"] })).toEqual({});
    expect(changedValues(original, { ...form, phone: "0912", enabled: 0 })).toEqual({ phone: "0912", enabled: 0 });
    expect(changedValues(original, { ...form, roles: ["Cataloger"], groups: [] })).toEqual({ roles: ["Cataloger"], groups: [] });
  });

  it("orders roles and toggles values without touching the old list", () => {
    expect(sortRoles(["Preservation Officer", "Document Admin", "Cataloger"])).toEqual(["Document Admin", "Cataloger", "Preservation Officer"]);
    const list = ["a"];
    expect(toggleValue(list, "b")).toEqual(["a", "b"]);
    expect(toggleValue(["a", "b"], "a")).toEqual(["b"]);
    expect(list).toEqual(["a"]);
  });

  it("explains why a user form cannot be sent", () => {
    expect(userProblem({ email: "bad", first_name: "x" }, true)).toBe("Nhập địa chỉ email hợp lệ");
    expect(userProblem({ email: "a@b.vn", first_name: " " }, true)).toBe("Nhập tên");
    expect(userProblem({ email: "", first_name: "x" }, false)).toBe("");
  });

  it("lets only a System Manager change an account that holds that role", () => {
    const me = { name: "admin@x.vn", roles: ["Document Admin"] };
    expect(canEditUser(original, me)).toBe(true);
    expect(canEditUser({ ...original, protected: true }, me)).toBe(false);
    expect(canEditUser({ ...original, protected: true }, { ...me, roles: ["System Manager"] })).toBe(true);
    expect(canEditUser(null, me)).toBe(false);
  });

  it("says what a role may do in words", () => {
    expect(permissionText({ read: 1, write: 1, create: 0, delete: 0 })).toBe("Xem, Sửa");
    expect(permissionText({ read: 1, create: 1, write: 1, delete: 1 })).toBe("Xem, Thêm, Sửa, Xóa");
    expect(permissionText({})).toBe("Không");
    expect(permissionText(undefined)).toBe("Không");
  });

  it("builds the log filters and the download link from the filled fields only", () => {
    expect(cleanLogFilters({ activity_type: "Xem", user: "", search: " abc ", date_from: "2026-01-01", extra: "x" })).toEqual({ activity_type: "Xem", search: "abc", date_from: "2026-01-01" });
    const url = new URL(logDownloadUrl({ user: "a@x.vn", search: "" }), "http://x");
    expect(url.pathname).toContain("logs.download_logs");
    expect(url.searchParams.get("user")).toBe("a@x.vn");
    expect(url.searchParams.has("search")).toBe(false);
  });

  it("keeps the last week out of a clean-up and wants the count typed back", () => {
    expect(latestPurgeDate(7, new Date(2026, 9, 8))).toBe("2026-10-01");
    expect(latestPurgeDate(7, new Date(2026, 0, 3))).toBe("2025-12-27");
    expect(purgeConfirmed("1.234", 1234)).toBe(true);
    expect(purgeConfirmed("1233", 1234)).toBe(false);
    expect(purgeConfirmed("", 0)).toBe(false);
  });

  it("pretty-prints log data and tolerates text that is not JSON", () => {
    expect(prettyJson('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(prettyJson("not json")).toBe("not json");
    expect(prettyJson("")).toBe("");
  });

  it("colours the monitor figures", () => {
    expect(serviceTone({ ok: true })).toBe("success");
    expect(serviceTone({ ok: false })).toBe("danger");
    expect(diskTone({ used_percent: 95 })).toBe("danger");
    expect(diskTone({ used_percent: 80 })).toBe("warning");
    expect(diskTone({ used_percent: 20 })).toBe("success");
    expect(diskTone(null)).toBe("muted");
    expect(indexTone({ total: 100, percent: 100, errors: 0 })).toBe("success");
    expect(indexTone({ total: 100, percent: 70, errors: 0 })).toBe("warning");
    expect(indexTone({ total: 100, percent: 100, errors: 2 })).toBe("danger");
    expect(queueText([{ name: "long", jobs: 1500 }, { name: "short", jobs: 0 }])).toBe("long: 1.500 · short: 0");
    expect(queueText(null)).toBe("—");
  });
});

describe("PreserveJobDrawer", () => {
  const integrity = { kind: "integrity", name: "IC-1", status: "Phát hiện lỗi", busy: false, percent: 100, check_type: "Toàn bộ", fonds: "", total_checked: 5, errors: 2, warnings: 1,
    summary: "Đã kiểm tra 5 tài liệu", restorable: 2, can_cancel: false, can_resume: false, can_delete: true, log: "" };
  const finding = (extra) => ({ name: "f1", document: "DOC-1", code: "FILE_MISSING", severity: "Lỗi", message: "Không còn tệp", restorable: 1, status: "Chưa xử lý", ...extra });

  it("lists the findings of a check and offers to go on to restoring", async () => {
    api.preservation.job.mockResolvedValue(integrity);
    api.preservation.findings.mockResolvedValue({ data: [finding(), finding({ name: "f2", code: "COUNTER_FONDS", severity: "Cảnh báo", document: null, restorable: 0 })], total: 2, page: 1, page_size: 50 });
    api.preservation.startRestore.mockResolvedValue({ name: "RS-1" });
    const wrapper = mount(PreserveJobDrawer, { props: { kind: "integrity", name: "IC-1", site: "x" }, global: { stubs: { Teleport: true, RouterLink: { template: "<a><slot /></a>" } } } });
    await flushPromises();
    expect(wrapper.text()).toContain("Mất tệp");
    expect(wrapper.text()).toContain("Sai bộ đếm phông");
    expect(wrapper.text()).toContain("Phục hồi được");
    const go = wrapper.findAll("button").find((b) => b.text().includes("Chuyển sang khôi phục"));
    expect(go.text()).toContain("2 tài liệu");
    await go.trigger("click");
    await flushPromises();
    expect(api.preservation.startRestore).toHaveBeenCalledWith({ check: "IC-1" });
    expect(wrapper.emitted("open")[0][0]).toEqual({ kind: "restore", name: "RS-1" });
    expect(wrapper.findAll("button").some((b) => b.text().includes("Sửa bộ đếm"))).toBe(true);
  });

  it("sets a finding aside and reloads the list", async () => {
    api.preservation.job.mockResolvedValue(integrity);
    api.preservation.findings.mockResolvedValue({ data: [finding()], total: 1, page: 1, page_size: 50 });
    api.preservation.setFinding.mockResolvedValue({});
    const wrapper = mount(PreserveJobDrawer, { props: { kind: "integrity", name: "IC-1", site: "x" }, global: { stubs: { Teleport: true, RouterLink: { template: "<a><slot /></a>" } } } });
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text() === "Bỏ qua").trigger("click");
    await flushPromises();
    expect(api.preservation.setFinding).toHaveBeenCalledWith("f1", "Đã bỏ qua");
    expect(api.preservation.findings).toHaveBeenCalledTimes(2);
  });

  it("shows a running backup's progress with a stop button, and the actions of a stopped one", async () => {
    const backup = { kind: "backup", name: "BK-1", status: "Đang chạy", busy: true, percent: 40, backup_type: "Cả hai", fonds: "", trigger: "Thủ công", phase: "",
      database: { file: "x.sql.gz", size_mb: 3, checksum: "ab" }, files: { total: 10, done: 4, failed: 0, size_mb: 1 }, can_cancel: true, can_resume: false, can_delete: false,
      has_database: true, has_files: true, items: [], items_total: 0, log: "", expires_on: null };
    api.preservation.job.mockResolvedValue(backup);
    api.preservation.cancel.mockResolvedValue({});
    const wrapper = mount(PreserveJobDrawer, { props: { kind: "backup", name: "BK-1", site: "x" }, global: { stubs: { Teleport: true, RouterLink: true } } });
    await flushPromises();
    expect(wrapper.find("[role=progressbar]").attributes("aria-valuenow")).toBe("40");
    await wrapper.findAll("button").find((b) => b.text().includes("Dừng")).trigger("click");
    expect(api.preservation.cancel).toHaveBeenCalledWith("backup", "BK-1");
    expect(wrapper.find("a[href*='download_backup']").exists()).toBe(true);
    api.preservation.job.mockResolvedValue({ ...backup, status: "Đã hủy", busy: false, percent: 40, can_cancel: false, can_resume: true, can_delete: true });
    await wrapper.setProps({ name: "" });
    await wrapper.setProps({ name: "BK-1" });
    await flushPromises();
    const texts = wrapper.findAll("button").map((b) => b.text());
    expect(texts.some((t) => t.includes("Chạy tiếp"))).toBe(true);
    expect(texts.some((t) => t.includes("Xóa"))).toBe(true);
  });

  it("asks for the site name before a database restore is run by the system", async () => {
    const backup = { kind: "backup", name: "BK-2", status: "Thành công", busy: false, percent: 100, backup_type: "Cơ sở dữ liệu", fonds: "", trigger: "", phase: "",
      database: { file: "d.sql.gz", size_mb: 3, checksum: "ab" }, files: { total: 0, done: 0, failed: 0, size_mb: 0 }, can_cancel: false, can_resume: false, can_delete: true,
      has_database: true, has_files: false, items: [], items_total: 0, log: "" };
    api.preservation.job.mockResolvedValue(backup);
    api.preservation.prepareDbRestore.mockResolvedValue({ verification: { ok: true, problems: [] }, batch: { name: "RS-9" }, runbook: "bench --site x restore", can_run: true, site: "x.example.com" });
    api.preservation.runRestore.mockResolvedValue({});
    const wrapper = mount(PreserveJobDrawer, { props: { kind: "backup", name: "BK-2", site: "x.example.com" }, global: { stubs: { Teleport: true, RouterLink: true } } });
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text().includes("Khôi phục từ bản này")).trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("bench --site x restore");
    const run = wrapper.findAll("button").find((b) => b.text().includes("Chạy khôi phục"));
    expect(run.attributes("disabled")).toBeDefined();
    await wrapper.find("input[type=text]").setValue("x.example.com");
    await flushPromises();
    const enabled = wrapper.findAll("button").find((b) => b.text().includes("Chạy khôi phục"));
    expect(enabled.attributes("disabled")).toBeUndefined();
    await enabled.trigger("click");
    await flushPromises();
    expect(api.preservation.runRestore).toHaveBeenCalledWith("RS-9", "x.example.com");
  });
});
